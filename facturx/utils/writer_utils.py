from datetime import datetime

from lxml import etree
from pypdf.generic import (DictionaryObject, NumberObject, NameObject, create_string_object, DecodedStreamObject)

from facturx.utils.logger import logger

def get_metadata_timestamp():
    now_dt = datetime.now()
    meta_date = now_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    return meta_date

def base_info2pdf_metadata(base_info):
    doc_type_name = 'Refund' if base_info['doc_type'] == '381' else 'Invoice'
    date_to_format = datetime.today() if not base_info.get('date', None) else base_info.get('date')
    date_str = datetime.strftime(date_to_format, '%Y-%m-%d')

    # Handle None values
    seller = base_info['seller'] or ''
    number = base_info['number'] or ''

    title = f"{seller}: {doc_type_name} {number}".strip(': ')
    subject = f"Factur-X {doc_type_name} {number} dated {date_str} issued by {seller}".strip()
    pdf_metadata = {
        'author': seller,
        'keywords': f"{doc_type_name}, Factur-X",
        'title': title,
        'subject': subject,
    }
    logger.debug('Converted base_info to pdf_metadata: %s', pdf_metadata)
    return pdf_metadata

def prepare_pdf_metadata_txt(pdf_metadata):
    pdf_date = get_pdf_timestamp()
    info_dict = {
        '/Author': pdf_metadata.get('author', ''),
        '/CreationDate': pdf_date,
        '/Creator': 'factur-x Python lib',
        '/Keywords': pdf_metadata.get('keywords', ''),
        '/ModDate': pdf_date,
        '/Subject': pdf_metadata.get('subject', ''),
        '/Title': pdf_metadata.get('title', ''),
    }
    return info_dict

def prepare_pdf_metadata_xml(xmp_level_str, xmp_filename, facturx_ext_schema_root, pdf_metadata):
    nsmap_x = {'x': 'adobe:ns:meta/'}
    nsmap_rdf = {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'}
    nsmap_dc = {'dc': 'http://purl.org/dc/elements/1.1/'}
    nsmap_pdf = {'pdf': 'http://ns.adobe.com/pdf/1.3/'}
    nsmap_xmp = {'xmp': 'http://ns.adobe.com/xap/1.0/'}
    nsmap_pdfaid = {'pdfaid': 'http://www.aiim.org/pdfa/ns/id/'}
    nsmap_fx = {'fx': 'urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#'}
    ns_x = '{%s}' % nsmap_x['x']
    ns_dc = '{%s}' % nsmap_dc['dc']
    ns_rdf = '{%s}' % nsmap_rdf['rdf']
    ns_pdf = '{%s}' % nsmap_pdf['pdf']
    ns_xmp = '{%s}' % nsmap_xmp['xmp']
    ns_pdfaid = '{%s}' % nsmap_pdfaid['pdfaid']
    ns_fx = '{%s}' % nsmap_fx['fx']
    ns_xml = '{http://www.w3.org/XML/1998/namespace}'

    root = etree.Element(ns_x + 'xmpmeta', nsmap=nsmap_x)
    rdf = etree.SubElement(root, ns_rdf + 'RDF', nsmap=nsmap_rdf)
    desc_pdfaid = etree.SubElement(rdf, ns_rdf + 'Description', nsmap=nsmap_pdfaid)
    desc_pdfaid.set(ns_rdf + 'about', '')
    etree.SubElement(desc_pdfaid, ns_pdfaid + 'part').text = '3'
    etree.SubElement(desc_pdfaid, ns_pdfaid + 'conformance').text = 'B'
    desc_dc = etree.SubElement(rdf, ns_rdf + 'Description', nsmap=nsmap_dc)
    desc_dc.set(ns_rdf + 'about', '')
    dc_title = etree.SubElement(desc_dc, ns_dc + 'title')
    dc_title_alt = etree.SubElement(dc_title, ns_rdf + 'Alt')
    dc_title_alt_li = etree.SubElement(dc_title_alt, ns_rdf + 'li')
    dc_title_alt_li.text = pdf_metadata.get('title', '')
    dc_title_alt_li.set(ns_xml + 'lang', 'x-default')
    dc_creator = etree.SubElement(desc_dc, ns_dc + 'creator')
    dc_creator_seq = etree.SubElement(dc_creator, ns_rdf + 'Seq')
    etree.SubElement(dc_creator_seq, ns_rdf + 'li').text = pdf_metadata.get('author', '')
    dc_desc = etree.SubElement(desc_dc, ns_dc + 'description')
    dc_desc_alt = etree.SubElement(dc_desc, ns_rdf + 'Alt')
    dc_desc_alt_li = etree.SubElement(dc_desc_alt, ns_rdf + 'li')
    dc_desc_alt_li.text = pdf_metadata.get('subject', '')
    dc_desc_alt_li.set(ns_xml + 'lang', 'x-default')
    desc_adobe = etree.SubElement(rdf, ns_rdf + 'Description', nsmap=nsmap_pdf)
    desc_adobe.set(ns_rdf + 'about', '')
    producer = etree.SubElement(desc_adobe, ns_pdf + 'Producer')
    producer.text = 'pypdf'
    desc_xmp = etree.SubElement(rdf, ns_rdf + 'Description', nsmap=nsmap_xmp)
    desc_xmp.set(ns_rdf + 'about', '')
    creator = etree.SubElement(desc_xmp, ns_xmp + 'CreatorTool')
    creator.text = 'factur-x python lib'
    timestamp = get_metadata_timestamp()
    etree.SubElement(desc_xmp, ns_xmp + 'CreateDate').text = timestamp
    etree.SubElement(desc_xmp, ns_xmp + 'ModifyDate').text = timestamp

    facturx_ext_schema_desc_xpath = facturx_ext_schema_root.xpath('//rdf:Description', namespaces=nsmap_rdf)
    rdf.append(facturx_ext_schema_desc_xpath[1])
    facturx_desc = etree.SubElement(rdf, ns_rdf + 'Description', nsmap=nsmap_fx)
    facturx_desc.set(ns_rdf + 'about', '')
    facturx_desc.set(ns_fx + 'ConformanceLevel', xmp_level_str)
    facturx_desc.set(ns_fx + 'DocumentFileName', xmp_filename)
    facturx_desc.set(ns_fx + 'DocumentType', 'INVOICE')
    facturx_desc.set(ns_fx + 'Version', '1.0')

    xml_str = etree.tostring(root, pretty_print=True, encoding="UTF-8", xml_declaration=False)
    head = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'.encode('utf-8')
    tail = '<?xpacket end="w"?>'.encode('utf-8')
    xml_final_str = head + xml_str + tail
    logger.debug('metadata XML:')
    return xml_final_str

def get_original_output_intents(original_pdf):
    output_intents = []
    try:
        pdf_root = original_pdf.trailer['/Root']
        ori_output_intents = pdf_root['/OutputIntents']
        logger.debug('output_intents_list=%s', ori_output_intents)
        for ori_output_intent in ori_output_intents:
            ori_output_intent_dict = ori_output_intent.get_object()
            logger.debug('ori_output_intents_dict=%s', ori_output_intent_dict)
            dest_output_profile_dict = ori_output_intent_dict['/DestOutputProfile'].get_object()
            output_intents.append((ori_output_intent_dict, dest_output_profile_dict))
    except:
        pass
    return output_intents

def get_pdf_timestamp(date=None):
    if date is None:
        date = datetime.now()
    pdf_date = date.strftime("D:%Y%m%d%H%M%S+00'00'")
    return pdf_date

def read_icc_profile(icc_path):
    with open(icc_path, "rb") as f:
        return f.read()

def create_output_intent(self, icc_bytes, output_condition="sRGB IEC61966-2.1"):
    # Create the ICC profile stream
    icc_stream = DecodedStreamObject()
    icc_stream.set_data(icc_bytes)
    icc_stream.update({
        NameObject("/N"): NumberObject(3),  # 3 components for RGB
    })
    icc_obj = self._add_object(icc_stream)

    # Build OutputIntent dictionary
    output_intent_dict = DictionaryObject({
        NameObject("/Type"): NameObject("/OutputIntent"),
        NameObject("/S"): NameObject("/GTS_PDFA1"),  # For PDF/A-3, GTS_PDFA1 is valid
        NameObject("/OutputConditionIdentifier"): create_string_object(output_condition),
        NameObject("/Info"): create_string_object(output_condition),
        NameObject("/DestOutputProfile"): icc_obj,
    })
    return self._add_object(output_intent_dict)
