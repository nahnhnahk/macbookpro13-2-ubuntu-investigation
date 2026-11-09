obj-m += applespi.o
# applespi_trace.h is included via TRACE_INCLUDE_PATH relative to the source dir
ccflags-y += -I$(src)

KVERSION ?= $(shell uname -r)
KDIR := /lib/modules/$(KVERSION)/build

all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) clean
