#!/usr/bin/env python
#
############################################################################
#
# MODULE:	    v.in.sos
# AUTHOR(S):	Ondrej Pesek <pesej.ondrek@gmail.com>
# PURPOSE:	    Import data from SOS server as a vector layer to GRASS GIS
# COPYRIGHT:	(C) 2017 Ondrej Pesek and the GRASS Development Team
#
#		This program is free software under the GNU General
#		Public License (>=v2). Read the file COPYING that
#		comes with GRASS for details.
#
#############################################################################

#%module
#% description: Load data from SOS server as a vector layer to GRASS GIS.
#% keyword: vector
#% keyword: import
#% keyword: SOS
#%end
#%option
#% key: url
#% type: string
#% description: Base URL starting with 'http' and ending in '?'
#% required: yes
#%end
#%option G_OPT_V_MAP
#% key: output
#% description: Name for output vector map
#% required: yes
#%end
#%option
#% key: offering
#% type: string
#% description: A collection of sensor used to conveniently group them up
#% required: yes
#%end
#%option
#% key: response_format
#% type: string
#% description: Format of data output
#% answer: text/xml;subtype="om/1.0.0"
#% required: yes
#%end
#%option
#% key: observed_properties
#% type: string
#% description: The phenomena that are observed
#% required: yes
#%end
#%option
#% key: procedure
#% type: string
#% description: Who provide the observations
#% required: yes
#%end
#%option
#% key: version
#% type: string
#% description: Version of SOS server
#% options: 1.0.0, 2.0.0
#% answer: 1.0.0
#%end

import sys
from grass.script import parser

def cleanup():
    pass

def main():
    print("I'm running")

    return 0


if __name__ == "__main__":
    options, flags = parser()
    main()
