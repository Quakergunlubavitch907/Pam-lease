/*
 * pam_lease.c — PAM module for pam-lease time-limited SSH access.
 *
 * Hooks implemented:
 *   pam_sm_authenticate  — deny auth if no valid lease exists
 *   pam_sm_open_session  — print expiry notice to user terminal
 *   pam_sm_setcred       — no-op, required by PAM ABI
 *   pam_sm_close_session — no-op, required by PAM ABI
 *
 * JSON is parsed manually via strstr/sscanf; no external libraries required.
 *
 * Build:
 *   gcc -O2 -fPIC -shared -Wl,-soname,pam_lease.so \
 *       -o pam_lease.so pam_lease.c -lpam
 *
 * Install:
 *   cp pam_lease.so /lib/security/
 *   chmod 644 /lib/security/pam_lease.so
 *
 * /etc/pam.d/sshd:
 *   auth     required pam_lease.so
 *   session  optional pam_lease.so
 */

#define PAM_SM_AUTH
#define PAM_SM_SESSION

#include <security/pam_modules.h>
#include <security/pam_ext.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define LEASE_DIR   "/run/pamlease"
#define MAX_PATH    512
#define MAX_BUF     4096

/*
 * read_lease — open and read the lease file for username into buf.
 * Returns the number of bytes read, or -1 on failure.
 */
static int read_lease(const char *username, char *buf, size_t bufsize)
{
    char path[MAX_PATH];
    int n;

    if (snprintf(path, sizeof(path), "%s/%s.lease", LEASE_DIR, username)
            >= (int)sizeof(path))
        return -1;

    FILE *f = fopen(path, "r");
    if (!f)
        return -1;

    n = (int)fread(buf, 1, bufsize - 1, f);
    fclose(f);

    if (n < 0)
        return -1;

    buf[n] = '\0';
    return n;
}

/*
 * parse_expires_at — locate "expires_at" in a JSON blob and parse the
 * ISO-8601 datetime value into *tm_out.
 * Returns 0 on success, -1 on failure.
 */
static int parse_expires_at(const char *json, struct tm *tm_out)
{
    const char *key;
    const char *colon;
    const char *q1;
    int y, mo, d, h, mi, s;

    key = strstr(json, "\"expires_at\"");
    if (!key)
        return -1;

    /* Advance past the key string. */
    key += strlen("\"expires_at\"");

    /* Find the colon separating key from value. */
    colon = strchr(key, ':');
    if (!colon)
        return -1;

    /* Find the opening quote of the datetime value. */
    q1 = strchr(colon, '"');
    if (!q1)
        return -1;
    q1++; /* skip the opening quote */

    if (sscanf(q1, "%d-%d-%dT%d:%d:%d", &y, &mo, &d, &h, &mi, &s) != 6)
        return -1;

    memset(tm_out, 0, sizeof(*tm_out));
    tm_out->tm_year  = y - 1900;
    tm_out->tm_mon   = mo - 1;
    tm_out->tm_mday  = d;
    tm_out->tm_hour  = h;
    tm_out->tm_min   = mi;
    tm_out->tm_sec   = s;
    tm_out->tm_isdst = -1; /* let mktime determine DST */

    return 0;
}

/*
 * pam_sm_authenticate — grant or deny authentication based on lease validity.
 *
 * Returns PAM_AUTH_ERR when:
 *   - no lease file exists for the user
 *   - the lease file cannot be parsed
 *   - the lease has expired
 *
 * Returns PAM_SUCCESS when the lease is present and valid.
 */
PAM_EXTERN int pam_sm_authenticate(pam_handle_t *pamh, int flags,
                                    int argc, const char **argv)
{
    const char *username = NULL;
    char buf[MAX_BUF];
    struct tm tm_expires;
    time_t expires;
    time_t now;

    (void)argc;
    (void)argv;
    (void)flags;

    if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || !username)
        return PAM_AUTH_ERR;

    if (read_lease(username, buf, sizeof(buf)) < 0)
        return PAM_AUTH_ERR;

    if (parse_expires_at(buf, &tm_expires) < 0)
        return PAM_AUTH_ERR;

    expires = mktime(&tm_expires);
    now     = time(NULL);

    if (now >= expires)
        return PAM_AUTH_ERR;

    return PAM_SUCCESS;
}

/*
 * pam_sm_open_session — print a session-expiry notice to the user terminal.
 *
 * Always returns PAM_SUCCESS — session open is never blocked here.
 * The message is delivered via pam_info(), which writes to the user's TTY.
 */
PAM_EXTERN int pam_sm_open_session(pam_handle_t *pamh, int flags,
                                    int argc, const char **argv)
{
    const char *username = NULL;
    char buf[MAX_BUF];
    struct tm tm_expires;
    time_t expires;
    time_t now;
    long secs_left;
    long mins_left;
    char time_str[32];
    char msg[256];

    (void)argc;
    (void)argv;
    (void)flags;

    if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || !username)
        return PAM_SUCCESS;

    if (read_lease(username, buf, sizeof(buf)) < 0)
        return PAM_SUCCESS;

    if (parse_expires_at(buf, &tm_expires) < 0)
        return PAM_SUCCESS;

    expires = mktime(&tm_expires);
    now     = time(NULL);

    if (now >= expires)
        return PAM_SUCCESS;

    secs_left = (long)(expires - now);
    mins_left = secs_left / 60;

    strftime(time_str, sizeof(time_str), "%H:%M:%S", &tm_expires);

    snprintf(msg, sizeof(msg),
             "Your session will expire in %ld minute%s (at %s).",
             mins_left,
             mins_left == 1 ? "" : "s",
             time_str);

    pam_info(pamh, "%s", msg);

    return PAM_SUCCESS;
}

/*
 * pam_sm_setcred — no-op, required to satisfy the PAM auth module ABI.
 */
PAM_EXTERN int pam_sm_setcred(pam_handle_t *pamh, int flags,
                               int argc, const char **argv)
{
    (void)pamh;
    (void)flags;
    (void)argc;
    (void)argv;
    return PAM_SUCCESS;
}

/*
 * pam_sm_close_session — no-op, required to satisfy the PAM session module ABI.
 */
PAM_EXTERN int pam_sm_close_session(pam_handle_t *pamh, int flags,
                                     int argc, const char **argv)
{
    (void)pamh;
    (void)flags;
    (void)argc;
    (void)argv;
    return PAM_SUCCESS;
}
