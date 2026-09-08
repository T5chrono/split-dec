"""The CA that signs the Supabase pooler's server certificate.

Embedded as a string rather than shipped as a `.crt` alongside it. The API is
one Vercel function built by a Python runtime that decides for itself which
non-source files come along; a certificate that failed to be bundled would be
a hard outage on the next deploy, and a `.py` file cannot fail to be bundled.

**Why this is needed at all**: the pooler does *not* present a publicly
trusted certificate. It serves `CN=*.pooler.supabase.com` issued by
`Supabase Intermediate 2021 CA` under `Supabase Root 2021 CA`, which is
Supabase's own root and is in no public trust store — so `certifi`, or the
operating system's bundle on its own, cannot verify it. `db.py` trusts this
root *in addition to* the system defaults, so the day Supabase moves the
pooler onto a public CA nothing here has to change.

Observed on the live pooler (2026-09-08):

    openssl s_client -connect aws-0-eu-west-3.pooler.supabase.com:6543 \
        -starttls postgres -showcerts

    subject   C=US, ST=Delware, L=New Castle, O=Supabase Inc,
              CN=Supabase Root 2021 CA
    serial    6CBC4CA1DEB63F692D0A2024C67289C2D13D54F6
    valid     2021-04-28 .. 2031-04-26
    SHA-256   80:70:25:AD:50:D4:ED:21:9D:2C:9C:7D:29:9C:00:4F:
              82:4E:B0:0C:F7:F6:5A:FE:F6:07:D0:7B:72:E6:CA:FA

`tests/test_db_tls.py` re-derives that fingerprint from the text below, so
editing this constant is a test failure rather than a silent change of who the
function is willing to talk to. Supabase hands the same file out per project
under Project Settings -> Database -> SSL Configuration; compare fingerprints
there rather than trusting this file's provenance on faith.

Expiry is 2031, which is far enough away to be someone else's problem and
close enough to be worth an entry in `docs/supply-chain.md` -- the rotation
lands as a connection failure, not a warning.
"""

# Supabase Root 2021 CA.
SUPABASE_ROOT_2021_CA_PEM = """\
-----BEGIN CERTIFICATE-----
MIIDxDCCAqygAwIBAgIUbLxMod62P2ktCiAkxnKJwtE9VPYwDQYJKoZIhvcNAQEL
BQAwazELMAkGA1UEBhMCVVMxEDAOBgNVBAgMB0RlbHdhcmUxEzARBgNVBAcMCk5l
dyBDYXN0bGUxFTATBgNVBAoMDFN1cGFiYXNlIEluYzEeMBwGA1UEAwwVU3VwYWJh
c2UgUm9vdCAyMDIxIENBMB4XDTIxMDQyODEwNTY1M1oXDTMxMDQyNjEwNTY1M1ow
azELMAkGA1UEBhMCVVMxEDAOBgNVBAgMB0RlbHdhcmUxEzARBgNVBAcMCk5ldyBD
YXN0bGUxFTATBgNVBAoMDFN1cGFiYXNlIEluYzEeMBwGA1UEAwwVU3VwYWJhc2Ug
Um9vdCAyMDIxIENBMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqQXW
QyHOB+qR2GJobCq/CBmQ40G0oDmCC3mzVnn8sv4XNeWtE5XcEL0uVih7Jo4Dkx1Q
DmGHBH1zDfgs2qXiLb6xpw/CKQPypZW1JssOTMIfQppNQ87K75Ya0p25Y3ePS2t2
GtvHxNjUV6kjOZjEn2yWEcBdpOVCUYBVFBNMB4YBHkNRDa/+S4uywAoaTWnCJLUi
cvTlHmMw6xSQQn1UfRQHk50DMCEJ7Cy1RxrZJrkXXRP3LqQL2ijJ6F4yMfh+Gyb4
O4XajoVj/+R4GwywKYrrS8PrSNtwxr5StlQO8zIQUSMiq26wM8mgELFlS/32Uclt
NaQ1xBRizkzpZct9DwIDAQABo2AwXjALBgNVHQ8EBAMCAQYwHQYDVR0OBBYEFKjX
uXY32CztkhImng4yJNUtaUYsMB8GA1UdIwQYMBaAFKjXuXY32CztkhImng4yJNUt
aUYsMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQELBQADggEBAB8spzNn+4VU
tVxbdMaX+39Z50sc7uATmus16jmmHjhIHz+l/9GlJ5KqAMOx26mPZgfzG7oneL2b
VW+WgYUkTT3XEPFWnTp2RJwQao8/tYPXWEJDc0WVQHrpmnWOFKU/d3MqBgBm5y+6
jB81TU/RG2rVerPDWP+1MMcNNy0491CTL5XQZ7JfDJJ9CCmXSdtTl4uUQnSuv/Qx
Cea13BX2ZgJc7Au30vihLhub52De4P/4gonKsNHYdbWjg7OWKwNv/zitGDVDB9Y2
CMTyZKG3XEu5Ghl1LEnI3QmEKsqaCLv12BnVjbkSeZsMnevJPs1Ye6TjjJwdik5P
o/bKiIz+Fq8=
-----END CERTIFICATE-----
"""
