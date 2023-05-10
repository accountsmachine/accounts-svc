
FROM fedora:36

# 171 MB

RUN dnf update -y && dnf install -y python3-pip && \
    dnf install -y python3-pyOpenSSL python3-ldap python3-jwt python3-wheel && \
    dnf clean all

# 278MB

# Adds about 1GB.
#RUN dnf install -y gnucash

RUN mkdir /root/wheels/ && mkdir /usr/local/am
ADD dep-wheels/* /root/wheels/

# 285MB

RUN pip3 install /root/wheels/gnucash_uk_vat-* \
    /root/wheels/ixbrl_parse-* \
    /root/wheels/ixbrl_reporter-* \
    /root/wheels/jsonnet-* \
    && rm -rf /root/wheels/* && pip3 cache purge

# 354MB

# Not needed, all deps on the accounts-svc wheel.
# RUN pip3 install py-dmidecode && \
#     pip3 install aiohttp && \
#     pip3 install firebase_admin && \
#     pip3 install secrets && \
#     pip3 install stripe && \
#     pip3 install piecash && \
#     pip3 install rdflib && \
#     pip3 cache purge

# 354MB

ADD ixbrl-reporter-jsonnet/ /usr/local/am/ixbrl-reporter-jsonnet/
ADD base /usr/local/am/base/

ADD wheels/* /root/wheels/
RUN pip3 install /root/wheels/accounts_svc-* \
    && rm -rf /root/wheels \
    && pip3 cache purge 

# 470MB

RUN ln -s /configs/accounts-svc-config /usr/local/am/config.json 

WORKDIR /usr/local/am

CMD am-svc config.json
EXPOSE 8080

# 470MB

