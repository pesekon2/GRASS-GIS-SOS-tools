MODULE_TOPDIR =../..

PGM = sos

SUBDIRS = libsos \
	v.in.sos \
	r.in.sos \
	t.vect.in.sos \
	t.rast.in.sos \

include $(MODULE_TOPDIR)/include/Make/Dir.make

default: parsubdirs htmldir

install: installsubdirs
	$(INSTALL_DATA) $(PGM).html $(INST_DIR)/docs/html/
