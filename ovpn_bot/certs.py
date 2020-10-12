from datetime import datetime
from logging import getLogger
from typing import Iterable

from OpenSSL.crypto import (
    load_certificate, load_privatekey, FILETYPE_PEM, X509, PKey, TYPE_RSA, X509Req,
    dump_privatekey, dump_certificate_request, dump_certificate, load_certificate_request, CRL,
    Revoked
)

log = getLogger(__name__)


def create_cert_manager(config):
    pki_config = config["pki"]
    ca = load_certificate(FILETYPE_PEM, read_file(pki_config["ca"]))
    cert = load_certificate(FILETYPE_PEM, read_file(pki_config["cert"]))
    pkey = load_privatekey(FILETYPE_PEM, read_file(pki_config["pkey"]), pki_config["passphrase"])
    tls_auth = read_file(pki_config["tls_auth"])
    return CertManager(ca, cert, pkey, tls_auth)


def read_file(filename: str) -> bytes:
    with  open(filename, "rb") as file:
        return file.read()


def write_file(filename: str, buffer: bytes):
    with open(filename, "wb") as file:
        file.write(buffer)


def dump_key(pkey: PKey) -> str:
    return dump_privatekey(FILETYPE_PEM, pkey).decode("utf-8")


def load_key(buffer: str) -> PKey:
    return load_privatekey(FILETYPE_PEM, buffer.encode("utf-8"))


def dump_cert_req(cert_req: X509Req) -> str:
    return dump_certificate_request(FILETYPE_PEM, cert_req).decode("utf-8")


def load_cert_req(buffer: str) -> X509Req:
    return load_certificate_request(FILETYPE_PEM, buffer.encode("utf-8"))


def dump_cert(cert: X509) -> str:
    return dump_certificate(FILETYPE_PEM, cert).decode("utf-8")


def load_cert(buffer: str) -> X509:
    return load_certificate(FILETYPE_PEM, buffer.encode("utf-8"))


class CertManager:
    def __init__(self, ca: X509, cert: X509, pkey: PKey, tls_auth: bytes):
        self.__ca = ca
        self.__cert = cert
        self.__pkey = pkey
        self.__tls_auth = tls_auth

    def dump_ca(self):
        return dump_cert(self.__ca)

    def dump_root_cert(self):
        return dump_cert(self.__cert)

    def dump_tls_auth(self):
        return self.__tls_auth.decode("utf-8")

    def create_private_key(self) -> PKey:
        pkey = PKey()
        pkey.generate_key(TYPE_RSA, self.__pkey.bits())
        return pkey

    def create_certificate_request(self, common_name, pkey) -> X509Req:
        cert_req = X509Req()
        cert_req.set_pubkey(pkey)
        subject = cert_req.get_subject()
        subject.countryName = self.__cert.get_subject().countryName
        subject.stateOrProvinceName = self.__cert.get_subject().stateOrProvinceName
        subject.localityName = self.__cert.get_subject().localityName
        subject.organizationName = self.__cert.get_subject().organizationName
        subject.organizationalUnitName = self.__cert.get_subject().organizationalUnitName
        subject.emailAddress = self.__cert.get_subject().emailAddress
        subject.commonName = common_name
        cert_req.sign(self.__pkey, "sha256")
        return cert_req

    def sign_certificate_request(self, cert_req: X509Req, serial_number: int) -> X509:
        cert = X509()
        cert.set_issuer(self.__cert.get_subject())
        cert.set_pubkey(cert_req.get_pubkey())
        cert.set_subject(cert_req.get_subject())
        cert.set_serial_number(serial_number)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)
        cert.sign(self.__pkey, "sha256")
        return cert

    def create_crl(self, serial_numbers: Iterable[int]) -> bytes:
        timestamp = (datetime.utcnow().strftime("%Y%m%d%H%M%S") + "Z").encode("utf-8")
        crl = CRL()
        for serial_number in serial_numbers:
            revoked = Revoked()
            revoked.set_serial(hex(serial_number)[2:].encode("utf-8"))
            revoked.set_rev_date(timestamp)
            revoked.set_reason(b"cessationOfOperation")
            crl.add_revoked(revoked)
        return crl.export(self.__cert, self.__pkey, FILETYPE_PEM, 1, b"sha256")
