# -*- Mode:python; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
#
# Copyright (C) 2014-2018 Regents of the University of California.
# Author: Adeola Bannis <thecodemaiden@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# A copy of the GNU Lesser General Public License is in the file COPYING.

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from pyndn import Name
from pyndn import Data
from pyndn import ContentType
from pyndn import KeyLocatorType
from pyndn import Sha256WithRsaSignature
from pyndn import GenericSignature
from pyndn.encoding import TlvWireFormat
from pyndn.lp.lp_packet import LpPacket
from pyndn.util import Blob
from .test_utils import dump, CredentialStorage
import unittest as ut

# use Python 3's mock library if it's available
try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

codedData = Blob(bytearray([
0x06, 0xCE, # NDN Data
  0x07, 0x0A, 0x08, 0x03, 0x6E, 0x64, 0x6E, 0x08, 0x03, 0x61, 0x62, 0x63, # Name
  0x14, 0x0A, # MetaInfo
    0x19, 0x02, 0x13, 0x88, # FreshnessPeriod
    0x1A, 0x04, # FinalBlockId
      0x08, 0x02, 0x00, 0x09, # NameComponent
  0x15, 0x08, 0x53, 0x55, 0x43, 0x43, 0x45, 0x53, 0x53, 0x21, # Content
  0x16, 0x28, # SignatureInfo
    0x1B, 0x01, 0x01, # SignatureType
    0x1C, 0x23, # KeyLocator
      0x07, 0x21, # Name
        0x08, 0x08, 0x74, 0x65, 0x73, 0x74, 0x6E, 0x61, 0x6D, 0x65,
        0x08, 0x03, 0x4B, 0x45, 0x59,
        0x08, 0x07, 0x44, 0x53, 0x4B, 0x2D, 0x31, 0x32, 0x33,
        0x08, 0x07, 0x49, 0x44, 0x2D, 0x43, 0x45, 0x52, 0x54,
  0x17, 0x80, # SignatureValue
    0x1A, 0x03, 0xC3, 0x9C, 0x4F, 0xC5, 0x5C, 0x36, 0xA2, 0xE7, 0x9C, 0xEE, 0x52, 0xFE, 0x45, 0xA7,
    0xE1, 0x0C, 0xFB, 0x95, 0xAC, 0xB4, 0x9B, 0xCC, 0xB6, 0xA0, 0xC3, 0x4A, 0xAA, 0x45, 0xBF, 0xBF,
    0xDF, 0x0B, 0x51, 0xD5, 0xA4, 0x8B, 0xF2, 0xAB, 0x45, 0x97, 0x1C, 0x24, 0xD8, 0xE2, 0xC2, 0x8A,
    0x4D, 0x40, 0x12, 0xD7, 0x77, 0x01, 0xEB, 0x74, 0x35, 0xF1, 0x4D, 0xDD, 0xD0, 0xF3, 0xA6, 0x9A,
    0xB7, 0xA4, 0xF1, 0x7F, 0xA7, 0x84, 0x34, 0xD7, 0x08, 0x25, 0x52, 0x80, 0x8B, 0x6C, 0x42, 0x93,
    0x04, 0x1E, 0x07, 0x1F, 0x4F, 0x76, 0x43, 0x18, 0xF2, 0xF8, 0x51, 0x1A, 0x56, 0xAF, 0xE6, 0xA9,
    0x31, 0xCB, 0x6C, 0x1C, 0x0A, 0xA4, 0x01, 0x10, 0xFC, 0xC8, 0x66, 0xCE, 0x2E, 0x9C, 0x0B, 0x2D,
    0x7F, 0xB4, 0x64, 0xA0, 0xEE, 0x22, 0x82, 0xC8, 0x34, 0xF7, 0x9A, 0xF5, 0x51, 0x12, 0x2A, 0x84,
1
  ]))

experimentalSignatureType = 100
experimentalSignatureInfo = Blob(bytearray([
0x16, 0x08, # SignatureInfo
  0x1B, 0x01, experimentalSignatureType, # SignatureType
  0x81, 0x03, 1, 2, 3 # Experimental info
  ]))

experimentalSignatureInfoNoSignatureType = Blob(bytearray([
0x16, 0x05, # SignatureInfo
  0x81, 0x03, 1, 2, 3 # Experimental info
  ]))

experimentalSignatureInfoBadTlv = Blob(bytearray([
0x16, 0x08, # SignatureInfo
  0x1B, 0x01, experimentalSignatureType, # SignatureType
  0x81, 0x10, 1, 2, 3 # Bad TLV encoding (length 0x10 doesn't match the value length.
  ]))

CONGESTION_MARK_PACKET = Blob(bytearray([
  0x64, 0xfd, 0x03, 0x5f, # LpPacket
    0xfd, 0x03, 0x40, 0x01, 0x01, # CongestionMark = 1
    0x50, 0xfd, 0x03, 0x56, # Fragment
      0x06, 0xfd, 0x03, 0x52, # NDN Data
        0x07, 0x18, 0x08, 0x04, 0x74, 0x65, 0x73, 0x74, 0x08, 0x09, 0xfd, 0x00, 0x00, 0x01, 0x62, 0xd5,
        0x29, 0x3f, 0xa8, 0x08, 0x05, 0x00, 0x00, 0x01, 0x57, 0xc3, 0x14, 0x0d, 0x19, 0x02, 0x27, 0x10,
        0x1a, 0x07, 0x08, 0x05, 0x00, 0x00, 0x02, 0xda, 0xcc, 0x15, 0xfd, 0x01, 0xf4, 0x65, 0x64, 0x20,
        0x43, 0x72, 0x79, 0x70, 0x74, 0x6f, 0x20, 0x74, 0x6f, 0x20, 0x6e, 0x6f, 0x74, 0x20, 0x63, 0x6c,
        0x61, 0x73, 0x68, 0x20, 0x77, 0x69, 0x74, 0x68, 0x20, 0x74, 0x68, 0x65, 0x20, 0x62, 0x72, 0x6f,
        0x77, 0x73, 0x65, 0x72, 0x27, 0x73, 0x20, 0x63, 0x72, 0x79, 0x70, 0x74, 0x6f, 0x2e, 0x73, 0x75,
        0x62, 0x74, 0x6c, 0x65, 0x2e, 0x0a, 0x2f, 0x2a, 0x2a, 0x20, 0x40, 0x69, 0x67, 0x6e, 0x6f, 0x72,
        0x65, 0x20, 0x2a, 0x2f, 0x0a, 0x76, 0x61, 0x72, 0x20, 0x63, 0x6f, 0x6e, 0x73, 0x74, 0x61, 0x6e,
        0x74, 0x73, 0x20, 0x3d, 0x20, 0x72, 0x65, 0x71, 0x75, 0x69, 0x72, 0x65, 0x28, 0x27, 0x63, 0x6f,
        0x6e, 0x73, 0x74, 0x61, 0x6e, 0x74, 0x73, 0x27, 0x29, 0x3b, 0x20, 0x2f, 0x2a, 0x2a, 0x20, 0x40,
        0x69, 0x67, 0x6e, 0x6f, 0x72, 0x65, 0x20, 0x2a, 0x2f, 0x0a, 0x76, 0x61, 0x72, 0x20, 0x43, 0x72,
        0x79, 0x70, 0x74, 0x6f, 0x20, 0x3d, 0x20, 0x72, 0x65, 0x71, 0x75, 0x69, 0x72, 0x65, 0x28, 0x27,
        0x2e, 0x2e, 0x2f, 0x2e, 0x2e, 0x2f, 0x63, 0x72, 0x79, 0x70, 0x74, 0x6f, 0x2e, 0x6a, 0x73, 0x27,
        0x29, 0x3b, 0x20, 0x2f, 0x2a, 0x2a, 0x20, 0x40, 0x69, 0x67, 0x6e, 0x6f, 0x72, 0x65, 0x20, 0x2a,
        0x2f, 0x0a, 0x76, 0x61, 0x72, 0x20, 0x4b, 0x65, 0x79, 0x54, 0x79, 0x70, 0x65, 0x20, 0x3d, 0x20,
        0x72, 0x65, 0x71, 0x75, 0x69, 0x72, 0x65, 0x28, 0x27, 0x2e, 0x2e, 0x2f, 0x73, 0x65, 0x63, 0x75,
        0x72, 0x69, 0x74, 0x79, 0x2d, 0x74, 0x79, 0x70, 0x65, 0x73, 0x27, 0x29, 0x2e, 0x4b, 0x65, 0x79,
        0x54, 0x79, 0x70, 0x65, 0x3b, 0x20, 0x2f, 0x2a, 0x2a, 0x20, 0x40, 0x69, 0x67, 0x6e, 0x6f, 0x72,
        0x65, 0x20, 0x2a, 0x2f, 0x0a, 0x76, 0x61, 0x72, 0x20, 0x45, 0x6e, 0x63, 0x72, 0x79, 0x70, 0x74,
        0x41, 0x6c, 0x67, 0x6f, 0x72, 0x69, 0x74, 0x68, 0x6d, 0x54, 0x79, 0x70, 0x65, 0x20, 0x3d, 0x20,
        0x72, 0x65, 0x71, 0x75, 0x69, 0x72, 0x65, 0x28, 0x27, 0x2e, 0x2e, 0x2f, 0x2e, 0x2e, 0x2f, 0x65,
        0x6e, 0x63, 0x72, 0x79, 0x70, 0x74, 0x2f, 0x61, 0x6c, 0x67, 0x6f, 0x2f, 0x65, 0x6e, 0x63, 0x72,
        0x79, 0x70, 0x74, 0x2d, 0x70, 0x61, 0x72, 0x61, 0x6d, 0x73, 0x2e, 0x6a, 0x73, 0x27, 0x29, 0x2e,
        0x45, 0x6e, 0x63, 0x72, 0x79, 0x70, 0x74, 0x41, 0x6c, 0x67, 0x6f, 0x72, 0x69, 0x74, 0x68, 0x6d,
        0x54, 0x79, 0x70, 0x65, 0x3b, 0x20, 0x2f, 0x2a, 0x2a, 0x20, 0x40, 0x69, 0x67, 0x6e, 0x6f, 0x72,
        0x65, 0x20, 0x2a, 0x2f, 0x0a, 0x76, 0x61, 0x72, 0x20, 0x44, 0x69, 0x67, 0x65, 0x73, 0x74, 0x41,
        0x6c, 0x67, 0x6f, 0x72, 0x69, 0x74, 0x68, 0x6d, 0x20, 0x3d, 0x20, 0x72, 0x65, 0x71, 0x75, 0x69,
        0x72, 0x65, 0x28, 0x27, 0x2e, 0x2e, 0x2f, 0x73, 0x65, 0x63, 0x75, 0x72, 0x69, 0x74, 0x79, 0x2d,
        0x74, 0x79, 0x70, 0x65, 0x73, 0x2e, 0x6a, 0x73, 0x27, 0x29, 0x2e, 0x44, 0x69, 0x67, 0x65, 0x73,
        0x74, 0x41, 0x6c, 0x67, 0x6f, 0x72, 0x69, 0x74, 0x68, 0x6d, 0x3b, 0x20, 0x2f, 0x2a, 0x2a, 0x20,
        0x40, 0x69, 0x67, 0x6e, 0x6f, 0x72, 0x65, 0x20, 0x2a, 0x2f, 0x0a, 0x76, 0x61, 0x72, 0x20, 0x44,
        0x61, 0x74, 0x61, 0x55, 0x74, 0x69, 0x6c, 0x73, 0x20, 0x3d, 0x20, 0x72, 0x65, 0x71, 0x75, 0x69,
        0x72, 0x65, 0x28, 0x27, 0x2e, 0x2e, 0x2f, 0x2e, 0x2e, 0x2f, 0x65, 0x6e, 0x63, 0x6f, 0x64, 0x69,
        0x6e, 0x67, 0x2f, 0x64, 0x61, 0x74, 0x61, 0x2d, 0x75, 0x74, 0x69, 0x6c, 0x73, 0x2e, 0x6a, 0x73,
        0x27, 0x16, 0x2b, 0x1b, 0x01, 0x01, 0x1c, 0x26, 0x07, 0x24, 0x08, 0x09, 0x6c, 0x6f, 0x63, 0x61,
        0x6c, 0x68, 0x6f, 0x73, 0x74, 0x08, 0x08, 0x6f, 0x70, 0x65, 0x72, 0x61, 0x74, 0x6f, 0x72, 0x08,
        0x03, 0x4b, 0x45, 0x59, 0x08, 0x08, 0xfb, 0x5d, 0x48, 0xd6, 0xf6, 0x2a, 0x80, 0x4a, 0x17, 0xfd,
        0x01, 0x00, 0x77, 0x1e, 0x6f, 0x13, 0x53, 0x08, 0x1b, 0xf6, 0x11, 0x2e, 0xaf, 0x82, 0x60, 0x86,
        0xb7, 0x64, 0x42, 0xf5, 0xf5, 0x7e, 0x66, 0xf1, 0xb4, 0x22, 0x51, 0x52, 0xaf, 0x3c, 0x73, 0x87,
        0xed, 0x73, 0xcf, 0xbf, 0x8b, 0x0c, 0x60, 0x61, 0xc7, 0x44, 0x5d, 0x4b, 0xb7, 0x2b, 0x13, 0x3b,
        0xa9, 0xab, 0x1a, 0x35, 0x71, 0x8b, 0x68, 0xd1, 0xf6, 0xa1, 0x10, 0xdd, 0x85, 0x1f, 0x07, 0x56,
        0x99, 0xcb, 0x5e, 0xba, 0x1c, 0x9b, 0x22, 0x34, 0xbd, 0x85, 0x54, 0xf3, 0x21, 0x01, 0xb1, 0x45,
        0x30, 0x98, 0xca, 0xcb, 0x24, 0x76, 0x1b, 0xe9, 0xa3, 0x47, 0x67, 0x3e, 0x27, 0x35, 0x33, 0x68,
        0x77, 0xb2, 0x83, 0x4c, 0xb9, 0x28, 0x42, 0x09, 0xeb, 0xbe, 0x50, 0x7b, 0xbd, 0xf2, 0xbc, 0xf6,
        0xa1, 0xdf, 0x43, 0x09, 0x55, 0x74, 0xb9, 0x55, 0x9f, 0xb2, 0x8f, 0x2b, 0xe5, 0xc6, 0x74, 0x38,
        0x5b, 0x38, 0x38, 0xbf, 0xed, 0x29, 0x4d, 0x9f, 0xaa, 0xcd, 0xef, 0xf4, 0x06, 0x20, 0x29, 0xad,
        0x6a, 0x14, 0xfa, 0x4a, 0xca, 0x9c, 0x8c, 0xe5, 0xc6, 0x98, 0x07, 0xa5, 0x18, 0xaf, 0x39, 0x15,
        0x2b, 0xb8, 0x28, 0x6f, 0xc6, 0x87, 0xc7, 0x03, 0x38, 0xbe, 0x3a, 0xeb, 0x0a, 0x9f, 0xb5, 0x71,
        0xc2, 0xa8, 0xd6, 0xc4, 0xad, 0xe6, 0x4d, 0x8c, 0x74, 0x08, 0x5d, 0x9b, 0xe7, 0xbf, 0xe2, 0xe0,
        0xe8, 0x1f, 0x44, 0x2c, 0x8e, 0xb2, 0x2a, 0x3b, 0x9c, 0xf0, 0xc1, 0xa0, 0xab, 0x8b, 0x2d, 0x66,
        0x07, 0x96, 0xde, 0xc0, 0x2a, 0x24, 0xce, 0x42, 0x5f, 0xcf, 0xd3, 0xc9, 0xc1, 0xc1, 0x83, 0x36,
        0xfd, 0x69, 0x58, 0x9f, 0x5c, 0x3f, 0x57, 0xcc, 0x5f, 0x7d, 0x14, 0x55, 0xa9, 0x35, 0x7f, 0xe3,
        0x9a, 0x36, 0x1a, 0x8b, 0xdc, 0xed, 0x1b, 0xd6, 0x45, 0x66, 0x05, 0x23, 0xa4, 0xda, 0x19, 0x85,
        0xfd, 0xe1
  ]))

def dumpData(data):
    result = []
    result.append(dump("name:", data.getName().toUri()))
    if len(data.getContent()) > 0:
        result.append(dump("content (raw):", str(data.getContent())))
        result.append(dump("content (hex):", data.getContent().toHex()))
    else:
        result.append(dump("content: <empty>"))
    if not data.getMetaInfo().getType() == ContentType.BLOB:
        result.append(dump("metaInfo.type:",
             "LINK" if data.getMetaInfo().getType() == ContentType.LINK
             else "KEY" if data.getMetaInfo().getType() == ContentType.KEY
             else "unknown"))
    result.append(dump("metaInfo.freshnessPeriod (milliseconds):",
         data.getMetaInfo().getFreshnessPeriod()
         if data.getMetaInfo().getFreshnessPeriod() >= 0 else "<none>"))
    result.append(dump("metaInfo.finalBlockId:",
         data.getMetaInfo().getFinalBlockId().toEscapedString()
         if len(data.getMetaInfo().getFinalBlockId().getValue()) > 0
         else "<none>"))
    signature = data.getSignature()
    if isinstance(signature, Sha256WithRsaSignature):
        result.append(dump("signature.signature:",
             "<none>" if len(signature.getSignature()) == 0
                      else signature.getSignature().toHex()))
        if signature.getKeyLocator().getType() is not None:
            if (signature.getKeyLocator().getType() ==
                KeyLocatorType.KEY_LOCATOR_DIGEST):
                result.append(dump("signature.keyLocator: KeyLocatorDigest:",
                     signature.getKeyLocator().getKeyData().toHex()))
            elif signature.getKeyLocator().getType() == KeyLocatorType.KEYNAME:
                result.append(dump("signature.keyLocator: KeyName:",
                     signature.getKeyLocator().getKeyName().toUri()))
            else:
                result.append(dump("signature.keyLocator: <unrecognized KeyLocatorType"))
        else:
            result.append(dump("signature.keyLocator: <none>"))
    return result



initialDump = ['name: /ndn/abc',
        'content (raw): SUCCESS!',
        'content (hex): 5355434345535321',
        'metaInfo.freshnessPeriod (milliseconds): 5000.0',
        'metaInfo.finalBlockId: %00%09',
        'signature.signature: 1a03c39c4fc55c36a2e79cee52fe45a7e10cfb95acb49bccb6a0c34aaa45bfbfdf0b51d5a48bf2ab45971c24d8e2c28a4d4012d77701eb7435f14dddd0f3a69ab7a4f17fa78434d7082552808b6c4293041e071f4f764318f2f8511a56afe6a931cb6c1c0aa40110fcc866ce2e9c0b2d7fb464a0ee2282c834f79af551122a84',
        'signature.keyLocator: KeyName: /testname/KEY/DSK-123/ID-CERT']


def dataDumpsEqual(d1, d2):
    #ignoring signature, see if two data dumps are equal
    unequal_set = set(d1) ^ set(d2)
    for field in unequal_set:
        if not field.startswith('signature.signature:'):
            return False
    return True

class TestDataDump(ut.TestCase):
    def setUp(self):
        self.credentials = CredentialStorage()
        self.freshData = self.createFreshData()

    def createFreshData(self):
        freshData = Data(Name("/ndn/abc"))
        freshData.setContent("SUCCESS!")
        freshData.getMetaInfo().setFreshnessPeriod(5000.0)
        freshData.getMetaInfo().setFinalBlockId(Name("/%00%09")[0])

        # Initialize the storage.
        return freshData

    def test_dump(self):
        data = Data()
        data.wireDecode(codedData)
        self.assertEqual(dumpData(data), initialDump, 'Initial dump does not have expected format')

    def test_encode_decode(self):
        data = Data()
        data.wireDecode(codedData)
        data.setContent(data.getContent())
        encoding = data.wireEncode()

        reDecodedData = Data()
        reDecodedData.wireDecode(encoding)
        self.assertEqual(dumpData(reDecodedData), initialDump, 'Re-decoded data does not match original dump')

    def test_empty_signature(self):
        # make sure nothing is set in the signature of newly created data
        data = Data()
        signature = data.getSignature()
        self.assertIsNone(signature.getKeyLocator().getType(), 'Key locator type on unsigned data should not be set')
        self.assertTrue(signature.getSignature().isNull(), 'Non-empty signature on unsigned data')

    def test_copy_fields(self):
        data = Data(self.freshData.getName())
        data.setContent(self.freshData.getContent())
        data.setMetaInfo(self.freshData.getMetaInfo())
        self.credentials.signData(data)
        freshDump = dumpData(data)
        self.assertTrue(dataDumpsEqual(freshDump, initialDump), 'Freshly created data does not match original dump')

    def test_verify(self):
        # we create 'mock' objects to replace callbacks
        # since we're not interested in the effect of the callbacks themselves
        failedCallback = Mock()
        verifiedCallback = Mock()

        self.credentials.signData(self.freshData)

        self.credentials.verifyData(self.freshData, verifiedCallback, failedCallback)
        self.assertEqual(failedCallback.call_count, 0, 'Signature verification failed')
        self.assertEqual(verifiedCallback.call_count, 1, 'Verification callback was not used.')

    def test_verify_ecdsa(self):
        # we create 'mock' objects to replace callbacks
        # since we're not interested in the effect of the callbacks themselves
        failedCallback = Mock()
        verifiedCallback = Mock()

        self.credentials.signData(self.freshData, self.credentials.ecdsaCertName)

        self.credentials.verifyData(self.freshData, verifiedCallback, failedCallback)
        self.assertEqual(failedCallback.call_count, 0, 'Signature verification failed')
        self.assertEqual(verifiedCallback.call_count, 1, 'Verification callback was not used.')

    def test_verify_digest_sha256(self):
        # We create 'mock' objects to replace callbacks since we're not
        # interested in the effect of the callbacks themselves.
        failedCallback = Mock()
        verifiedCallback = Mock()

        self.credentials.signDataWithSha256(self.freshData)

        self.credentials.verifyData(self.freshData, verifiedCallback, failedCallback)
        self.assertEqual(failedCallback.call_count, 0, 'Signature verification failed')
        self.assertEqual(verifiedCallback.call_count, 1, 'Verification callback was not used.')

    def test_generic_signature(self):
        # Test correct encoding.
        signature = GenericSignature()
        signature.setSignatureInfoEncoding(
          Blob(experimentalSignatureInfo, False), None)
        signatureValue = Blob([1, 2, 3, 4], False)
        signature.setSignature(signatureValue)

        self.freshData.setSignature(signature)
        encoding = self.freshData.wireEncode()

        decodedData = Data()
        decodedData.wireDecode(encoding)

        decodedSignature = decodedData.getSignature()
        self.assertEqual(decodedSignature.getTypeCode(), experimentalSignatureType)
        self.assertTrue(Blob(experimentalSignatureInfo, False).equals
                        (decodedSignature.getSignatureInfoEncoding()))
        self.assertTrue(signatureValue.equals(decodedSignature.getSignature()))

        # Test bad encoding.
        signature = GenericSignature()
        signature.setSignatureInfoEncoding(
          Blob(experimentalSignatureInfoNoSignatureType, False), None)
        signature.setSignature(signatureValue)
        self.freshData.setSignature(signature)
        gotError = True
        try:
            self.freshData.wireEncode()
            gotError = False
        except:
            pass
        if not gotError:
          self.fail("Expected encoding error for experimentalSignatureInfoNoSignatureType")

        signature = GenericSignature()
        signature.setSignatureInfoEncoding(
          Blob(experimentalSignatureInfoBadTlv, False), None)
        signature.setSignature(signatureValue)
        self.freshData.setSignature(signature)
        gotError = True
        try:
            self.freshData.wireEncode()
            gotError = False
        except:
            pass
        if not gotError:
          self.fail("Expected encoding error for experimentalSignatureInfoBadTlv")

    def test_full_name(self):
        data = Data()
        data.wireDecode(codedData)

        # Check the full name format.
        self.assertEqual(data.getFullName().size(), data.getName().size() + 1)
        self.assertEqual(data.getName(), data.getFullName().getPrefix(-1))
        self.assertEqual(data.getFullName().get(-1).getValue().size(), 32)

        # Check the independent digest calculation.
        sha256 = hashes.Hash(hashes.SHA256(), backend=default_backend())
        sha256.update(Blob(codedData).toBytes())
        newDigest = Blob(bytearray(sha256.finalize()), False)
        self.assertTrue(newDigest.equals(data.getFullName().get(-1).getValue()))

        # Check the expected URI.
        self.assertEqual(
          data.getFullName().toUri(), "/ndn/abc/sha256digest=" +
            "96556d685dcb1af04be4ae57f0e7223457d4055ea9b3d07c0d337bef4a8b3ee9")

        # Changing the Data packet should change the full name.
        saveFullName = Name(data.getFullName())
        data.setContent(Blob())
        self.assertNotEqual(data.getFullName().get(-1), saveFullName.get(-1))

    def test_congestion_mark(self):
        # Imitate onReceivedElement.
        lpPacket = LpPacket()
        # Set copy False so that the fragment is a slice which will be
        # copied below. The header fields are all integers and don't need to
        # be copied.
        TlvWireFormat.get().decodeLpPacket(lpPacket, CONGESTION_MARK_PACKET.buf(), False)
        element = lpPacket.getFragmentWireEncoding().buf()

        data = Data()
        data.wireDecode(element, TlvWireFormat.get())
        data.setLpPacket(lpPacket)

        self.assertEqual(1, data.getCongestionMark())

if __name__ == '__main__':
    ut.main(verbosity=2)
