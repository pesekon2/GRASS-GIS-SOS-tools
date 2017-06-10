#! /usr/bin/python

############################################################################
#
# MODULE:	    v.in.sos
# AUTHOR(S):	Ondrej Pesek <pesej.ondrek@gmail.com>
# PURPOSE:	    Load data from SOS server as a vector layer to GRASS GIS
# COPYRIGHT:	(C) 2017 Ondrej Pesek and the GRASS Development Team
#
#		This program is free software under the GNU General
#		Public License (>=v2). Read the file COPYING that
#		comes with GRASS for details.
#
#############################################################################


# %Module
# % description: Load data from SOS server as a vector layer to GRASS GIS.
# % keyword: vector
# % keyword: import
# % keyword: SOS
# %end
# %option
# % key: url
# % type: string
# % description: Base URL starting with 'http' and ending in '?'
# % required: yes
# %end


import sys
from subprocess import PIPE

import grass.script as grass


def main():
    print("I'm runniiiing")


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
