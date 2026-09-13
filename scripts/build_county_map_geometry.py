#!/usr/bin/env python3
"""Build offline public county/state map paths from Census 2019 KML archives."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
NS='{http://www.opengis.net/kml/2.2}'

def project(lon,lat):
    p1,p2,p0=map(math.radians,(29.5,45.5,37.5));n=(math.sin(p1)+math.sin(p2))/2
    c=math.cos(p1)**2+2*n*math.sin(p1);rho=math.sqrt(c-2*n*math.sin(math.radians(lat)))/n
    rho0=math.sqrt(c-2*n*math.sin(p0))/n;theta=n*math.radians(lon+96)
    return rho*math.sin(theta),-(rho0-rho*math.cos(theta))

def read_kml(path):
    with zipfile.ZipFile(str(path)) as archive:
        names=[n for n in archive.namelist() if n.endswith('.kml')]
        if len(names)!=1:raise ValueError('Expected one KML')
        root=ET.fromstring(archive.read(names[0]))
    result=[]
    for pm in root.iter(NS+'Placemark'):
        properties={s.attrib['name']:s.text for s in pm.iter(NS+'SimpleData')}
        rings=[]
        for polygon in pm.iter(NS+'Polygon'):
            for node in polygon.iter(NS+'coordinates'):
                points=[project(*map(float,token.split(',')[:2])) for token in node.text.split()]
                if len(points)>=4:rings.append(points)
        result.append((properties,rings))
    return result

def build(counties,states,footprint):
    with footprint.open() as h:wanted={r['fips'] for r in csv.DictReader(h)}
    county_data=[(p,r) for p,r in read_kml(counties) if p['GEOID'] in wanted]
    if {p['GEOID'] for p,r in county_data}!=wanted:raise ValueError('Public boundaries do not cover audited counties')
    state_data=[(p,r) for p,r in read_kml(states) if int(p['STATEFP'])<=56 and p['STATEFP'] not in ('02','15')]
    pts=[xy for p,rings in state_data for ring in rings for xy in ring]
    xmin=min(p[0] for p in pts);ymin=min(p[1] for p in pts);xmax=max(p[0] for p in pts);ymax=max(p[1] for p in pts)
    scale=min(960/(xmax-xmin),550/(ymax-ymin))
    def feature(properties,rings):
        r=[[(round((x-xmin)*scale+20,2),round((y-ymin)*scale+20,2)) for x,y in ring] for ring in rings]
        path=''.join('M'+'L'.join(str(x)+','+str(y) for x,y in ring)+'Z' for ring in r)
        pts=[xy for ring in r for xy in ring]
        return dict(id=properties['GEOID'],name=properties['NAME'],path=path,bounds=[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)])
    return dict(viewBox=[0,0,1000,590],counties=[feature(p,r) for p,r in county_data],states=[feature(p,r) for p,r in state_data],
      provenance=dict(source='U.S. Census Bureau, 2019 cartographic boundaries, 1:5,000,000',
        county_url='https://www2.census.gov/geo/tiger/GENZ2019/kml/cb_2019_us_county_5m.zip',
        state_url='https://www2.census.gov/geo/tiger/GENZ2019/kml/cb_2019_us_state_5m.zip',
        county_sha256=hashlib.sha256(counties.read_bytes()).hexdigest(),state_sha256=hashlib.sha256(states.read_bytes()).hexdigest(),
        display_projection='Spherical Albers equal-area; parallels 29.5/45.5, central longitude -96. Display only; modeling uses audited 2010 graph.'))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('counties',type=Path);p.add_argument('states',type=Path);p.add_argument('footprint',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    a.output.write_text(json.dumps(build(a.counties,a.states,a.footprint),separators=(',',':'))+'\n')
