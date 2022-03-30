
FROM fedora:35

RUN dnf update -y && dnf install -y python3-pip && \
    dnf install -y python3-pyOpenSSL python3-ldap python3-jwt && dnf clean all

RUN mkdir /root/wheels/ && mkdir /usr/local/am
ADD wheels/* /root/wheels/

RUN pip3 install /root/wheels/gnucash_uk_vat-* \
    /root/wheels/ixbrl_parse-* \
    /root/wheels/ixbrl_reporter-* \
    /root/wheels/jsonnet-* \
    /root/wheels/accounts_svc-* && rm -rf /root/wheels

ADD ixbrl-reporter-jsonnet/ /usr/local/am/ixbrl-reporter-jsonnet/
ADD base /usr/local/am/base/

ADD config-local.json /usr/local/am/config.json
ADD private.json pubkey1.pem pubkey2.pem /usr/local/am/

WORKDIR /usr/local/am

CMD am-svc config.json
EXPOSE 8080

