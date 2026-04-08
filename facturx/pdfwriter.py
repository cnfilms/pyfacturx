import hashlib
import io

from pypdf import PdfWriter, PdfReader
from pypdf.generic import (DictionaryObject, NumberObject, NameObject, create_string_object, ArrayObject,
                           DecodedStreamObject)

from facturx.utils.logger import logger
from facturx.utils.writer_utils import get_original_output_intents, base_info2pdf_metadata, get_pdf_timestamp, \
    read_icc_profile, create_output_intent, prepare_pdf_metadata_txt, prepare_pdf_metadata_xml

file_types = (io.IOBase,)
unicode = str

class FacturXPDFWriter(PdfWriter):
    def __init__(self, facturx, pdf_metadata=None):
        """Take a FacturX instance and write the XML to the attached PDF file"""

        super().__init__()
        self.factx = facturx

        original_pdf = PdfReader(facturx.pdf)
        # Extract /OutputIntents obj from original invoice
        output_intents = get_original_output_intents(original_pdf)
        self.append_pages_from_reader(original_pdf)

        original_pdf_id = original_pdf.trailer.get("/ID")
        logger.debug('original_pdf_id=%s', original_pdf_id)
        if original_pdf_id:
            self._ID = original_pdf_id

        if pdf_metadata is None:
            base_info = {
                'seller': self.factx['seller_name'],
                'number': self.factx['invoice_number'],
                'date': self.factx['date'],
                'doc_type': self.factx['type'],
            }
            pdf_metadata = base_info2pdf_metadata(base_info)
        else:
            # clean-up pdf_metadata dict
            for key, value in pdf_metadata.items():
                if not isinstance(value, (str, unicode)):
                    pdf_metadata[key] = ''

        self._update_metadata_add_attachment(pdf_metadata, output_intents)

    def _update_metadata_add_attachment(self, pdf_metadata, output_intents):
        # The entry for the file
        facturx_xml_str = self.factx.xml_str
        md5sum = hashlib.md5(facturx_xml_str).hexdigest()
        md5sum_obj = create_string_object(md5sum)
        params_dict = DictionaryObject({
            NameObject('/CheckSum'): md5sum_obj,
            NameObject('/ModDate'): create_string_object(get_pdf_timestamp()),
            NameObject('/Size'): NumberObject(len(facturx_xml_str)),
        })
        file_entry = DecodedStreamObject()
        file_entry.set_data(facturx_xml_str)  # here we integrate the file itself
        file_entry.update({
            NameObject("/Type"): NameObject("/EmbeddedFile"),
            NameObject("/Params"): params_dict,
            NameObject("/Subtype"): NameObject("/text/xml"),
        })
        file_entry_obj = self._add_object(file_entry)
        # The Filespec entry
        ef_dict = DictionaryObject({
            NameObject("/F"): file_entry_obj,
            NameObject('/UF'): file_entry_obj,
        })

        xmp_filename = self.factx.flavor.details['xmp_filename']
        fname_obj = create_string_object(xmp_filename)
        filespec_dict = DictionaryObject({
            NameObject("/AFRelationship"): NameObject("/Data"),
            NameObject("/Desc"): create_string_object("Factur-X Invoice"),
            NameObject("/Type"): NameObject("/Filespec"),
            NameObject("/F"): fname_obj,
            NameObject("/EF"): ef_dict,
            NameObject("/UF"): fname_obj,
        })
        filespec_obj = self._add_object(filespec_dict)

        # Create embedded files dictionary
        embedded_files_names_dict = DictionaryObject({
            NameObject("/Names"): ArrayObject([fname_obj, filespec_obj]),
        })
        embedded_files_dict = DictionaryObject({
            NameObject("/EmbeddedFiles"): embedded_files_names_dict,
        })

        # Handle OutputIntents
        res_output_intents = []
        for output_intent_dict, dest_output_profile_dict in output_intents:
            dest_output_profile_obj = self._add_object(dest_output_profile_dict)
            output_intent_dict.update({NameObject("/DestOutputProfile"): dest_output_profile_obj})
            output_intent_obj = self._add_object(output_intent_dict)
            res_output_intents.append(output_intent_obj)

        if not res_output_intents:
            # logger.info("No OutputIntent found, embedding sRGB ICC profile")
            icc_path = "/usr/share/color/icc/colord/sRGB.icc"
            icc_bytes = read_icc_profile(icc_path)
            output_intent_obj = create_output_intent(self, icc_bytes)
            res_output_intents.append(output_intent_obj)

        # Embed metadata XML
        xmp_level_str = self.factx.flavor.details['levels'][self.factx.flavor.level]['xmp_str']
        xmp_template = self.factx.flavor.get_xmp_xml()
        metadata_xml_str = prepare_pdf_metadata_xml(xmp_level_str, xmp_filename, xmp_template, pdf_metadata)
        metadata_file_entry = DecodedStreamObject()
        metadata_file_entry.set_data(metadata_xml_str)
        metadata_file_entry.update({
            NameObject('/Subtype'): NameObject('/XML'),
            NameObject('/Type'): NameObject('/Metadata'),
        })
        metadata_obj = self._add_object(metadata_file_entry)
        af_value_obj = self._add_object(ArrayObject([filespec_obj]))
        self._root_object.update({
            NameObject("/AF"): af_value_obj,
            NameObject("/Metadata"): metadata_obj,
            NameObject("/Names"): embedded_files_dict,
            NameObject("/PageMode"): NameObject("/UseAttachments"),
            NameObject("/OutputIntents"): ArrayObject(res_output_intents),
        })
        metadata_txt_dict = prepare_pdf_metadata_txt(pdf_metadata)
        self.add_metadata(metadata_txt_dict)
