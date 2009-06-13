#!/usr/bin/env python
#    genoshatest/xmltest.py - test cases for Genosha over XML
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

from genosha.SQL import dumpc, loadc, create_tables
import genoshatest
from sqlite3 import connect

__version__ = "0.1"
__author__ = "Shawn Sulma <genosha@470th.org>"

class GenoshaSQLTests ( genoshatest.GenoshaTests ) :
    def setUp ( self ) :
        self.conn = connect( ':memory:' )
        create_tables( self.conn.cursor() )
        self.conn.commit()
        self.marshal = lambda o : dumpc( o, self.conn )
        self.unmarshal = lambda o : loadc( o, self.conn )
        self.long = long
        self.unicode = unicode

    def tearDown( self ) :
        if self.conn :
            self.conn.close()

if __name__ == "__main__":
    unittest.main()
