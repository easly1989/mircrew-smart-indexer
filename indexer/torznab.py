"""
Torznab API implementation for indexer responses.
"""
import xml.etree.ElementTree as ET
from typing import List, Dict
from flask import Response
from datetime import datetime

# Register namespace prefixes
ET.register_namespace("torznab", "http://torznab.com/schemas/2015/feed")
ET.register_namespace("atom", "http://www.w3.org/2005/Atom")


def torznab_error(message: str) -> Response:
    """Return Torznab error response."""
    error_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<error code="100" description="{message}"/>'''
    return Response(error_xml, mimetype='application/xml')


def build_torznab_xml(results: List[Dict]) -> Response:
    """Build Torznab-compatible XML response from search results."""
    rss = ET.Element('rss', version='2.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = 'MIRCrew Smart'
    ET.SubElement(channel, 'description').text = 'MIRCrew Smart Indexer for TV Series'
    for result in results:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = result.get('title', 'Unknown')
        guid = f"mircrew-{result.get('thread_id', '0')}-{result.get('season', 0)}-{result.get('episode', 0)}"
        ET.SubElement(item, 'guid').text = guid
        ET.SubElement(item, 'link').text = result.get('thread_url', '')
        ET.SubElement(item, 'pubDate').text = result.get('publish_date', datetime.now().isoformat())
        ET.SubElement(item, 'size').text = str(result.get('size', 0))
        enclosure = ET.SubElement(item, 'enclosure')
        enclosure.set('url', result.get('magnet', ''))
        enclosure.set('type', 'application/x-bittorrent')
        enclosure.set('length', str(result.get('size', 0)))
        ET.SubElement(item, 'torznab:attr',
                      name='category',
                      value=str(result.get('category', '5000')))
        ET.SubElement(item, 'torznab:attr',
                      name='seeders',
                      value=str(result.get('seeders', 1)))
        ET.SubElement(item, 'torznab:attr',
                      name='peers',
                      value=str(result.get('peers', 0)))
        if 'season' in result and result['season']:
            ET.SubElement(item, 'torznab:attr',
                          name='season',
                          value=str(result['season']))
        if 'episode' in result and result['episode']:
            ET.SubElement(item, 'torznab:attr',
                          name='episode',
                          value=str(result['episode']))
    xml_str = ET.tostring(rss, encoding='unicode')
    return Response(xml_str, mimetype='application/xml')


def torznab_caps() -> Response:
    """Return Torznab capabilities XML."""
    caps_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<caps>
    <server version="1.0" title="MIRCrew Smart" />
    <limits max="100" default="25"/>
    <searching>
        <search available="yes" supportedParams="q,cat"/>
        <tv-search available="yes" supportedParams="q,season,ep,cat"/>
    </searching>
    <categories>
        <category id="2000" name="Movies"/>
        <category id="5000" name="TV">
            <subcat id="5070" name="Anime"/>
        </category>
        <category id="7000" name="Books"/>
        <category id="3000" name="Music"/>
    </categories>
</caps>'''
    return Response(caps_xml, mimetype='application/xml')


def torznab_test(indexer) -> Response:
    """Return Torznab response for test requests by performing test search."""
    results = indexer.search_mircrew_smart_tv('', None)
    return build_torznab_xml(results)


def torznab_search(indexer, request) -> Response:
    """Handle Torznab search requests."""
    query = request.args.get('q', '')
    season = request.args.get('season', '')
    season_int = int(season) if season.isdigit() else None
    results = indexer.search_mircrew_smart_tv(query, season_int)
    return build_torznab_xml(results)