#    genosha/json.py - XML serialization/deserialization for Genosha.
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
r"""genosha/xml.py provides an implemention of output to (and input from) xml serialization
for the genosha library.  It provides :mod:`pickle`-like capabilities, using an XML-like
syntax as the underlying serialization mechanism.
"""
#<object oid="<oid>" class="<class-name>" attribute="<attribute-name>" reference="<obj>">
#   <items>...</items>
#   <fields><field name="<name>"><value>...</value></field>...</fields>
#</object>
#<reference oid="<oid>"/>
#<primitive type="<type>"><[[CDATA...]]>...</primitive>
#<list>...</list>
#<dict><entry><key><[[CDATA...]]></key><value><[[CDATA...]]></value></entry>...</dict>

