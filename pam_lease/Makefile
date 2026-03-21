CC          := gcc
CFLAGS      := -O2 -fPIC -Wall -Wextra
LDFLAGS     := -shared -Wl,-soname,pam_lease.so
TARGET      := pam_lease.so
INSTALL_DIR := /lib/security
PAM_HEADER  := /usr/include/security/pam_appl.h

$(if $(wildcard $(PAM_HEADER)),,$(error \
  pam_appl.h not found. Install the PAM development headers: \
  Debian/Ubuntu: sudo apt install libpam-dev | \
  RHEL/Fedora:   sudo dnf install pam-devel | \
  Arch:          sudo pacman -S linux-pam))

.PHONY: all install uninstall clean

all: $(TARGET)

$(TARGET): pam_lease.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $< -lpam

install: $(TARGET)
	cp $(TARGET) $(INSTALL_DIR)/$(TARGET)
	chmod 644 $(INSTALL_DIR)/$(TARGET)
	@echo "Installed $(TARGET) to $(INSTALL_DIR)/$(TARGET)"

uninstall:
	rm -f $(INSTALL_DIR)/$(TARGET)
	@echo "Removed $(INSTALL_DIR)/$(TARGET)"

clean:
	rm -f $(TARGET)
