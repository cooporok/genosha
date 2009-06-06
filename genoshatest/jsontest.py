#!/usr/bin/env python
#    genoshatest/jsontest.py - test cases for Genosha over JSON
#    Copyright (C) 2009 Shawn Sulma <genosha@470th.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
import time, sys, unittest

import genosha
from genosha.JSON import dumps, loads
import genoshatest

__version__ = "0.1"
__author__ = "Shawn Sulma <genosha@470th.org>"

class GenoshaJSONTests ( genoshatest.GenoshaTests ) :
    def setUp ( self ) :
        self.marshal = dumps
        self.unmarshal = loads
        self.long = int
        self.unicode = str

if __name__ == "__main__":
    unittest.main()
