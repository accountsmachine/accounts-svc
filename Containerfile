
FROM fedora:35

# FIXME: Clean
RUN dnf update -y && dnf install -y python3-pip

RUN pip3 install ixbrl-reporter

RUN mkdir /usr/local/am/

ADD ixbrl-reporter-jsonnet/ /usr/local/am/ixbrl-reporter-jsonnet/
ADD base /usr/local/am/base/

RUN dnf install -y python3-pyOpenSSL python3-ldap python3-jwt

RUN mkdir /root/wheels/
ADD wheels/* /root/wheels/

RUN pip3 install /root/wheels/gnucash_uk_vat-*
RUN pip3 install /root/wheels/ixbrl_parse-*
RUN pip3 install /root/wheels/ixbrl_reporter-*
RUN pip3 install /root/wheels/jsonnet-*
RUN pip3 install /root/wheels/accounts_svc-*

RUN dnf clean all
RUN rm -rf /root/wheels

ADD config-local.json /usr/local/am/config.json
ADD private.json pubkey1.pem pubkey2.pem /usr/local/am/

WORKDIR /usr/local/am

CMD am-svc config.json
EXPOSE 8081

