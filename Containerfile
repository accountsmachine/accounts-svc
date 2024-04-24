
# At time of writing, chasing down a problem with pyOpenSSL incompatibility
# Appears to go away with downgrade Alpine 3.18 -> 3.17

FROM alpine:3.17 AS build

env PACKAGE_VERSION=0.0.0

RUN apk add --update --no-cache --no-progress make g++ gcc linux-headers
RUN apk add --update --no-cache --no-progress openldap-dev git
RUN apk add --update --no-cache --no-progress python3 py3-pip py3-wheel \
    python3-dev

RUN pip3 install GitPython

RUN mkdir /root/wheels

RUN pip3 wheel -w /root/wheels --no-deps netifaces

RUN pip3 wheel -w /root/wheels --no-deps jsonnet
RUN pip3 wheel -w /root/wheels --no-deps gnucash-uk-vat
RUN pip3 wheel -w /root/wheels --no-deps ixbrl-reporter
RUN pip3 wheel -w /root/wheels --no-deps ixbrl-parse
RUN pip3 wheel -w /root/wheels --no-deps python-ldap

COPY setup.py /root/accountsmachine/
COPY README.md /root/accountsmachine/
COPY scripts/ /root/accountsmachine/scripts/
COPY accountsmachine/ /root/accountsmachine/accountsmachine/

RUN (cd /root/accountsmachine && pip3 wheel -w /root/wheels --no-deps .)

FROM alpine:3.17

COPY --from=build /root/wheels /root/wheels

RUN apk add --update --no-cache --no-progress openldap python3 py3-pip \
      py3-aiohttp py3-rdflib py3-openssl

RUN pip3 install /root/wheels/gnucash_uk_vat-* \
    /root/wheels/ixbrl_parse-* \
    /root/wheels/ixbrl_reporter-* \
    /root/wheels/jsonnet-* \
    /root/wheels/netifaces-* \
    /root/wheels/python_ldap-* \
    /root/wheels/accounts_svc-* && \
    pip3 cache purge && \
    rm -rf /root/wheels

ADD ixbrl-reporter-jsonnet/ /usr/local/am/ixbrl-reporter-jsonnet/
ADD base /usr/local/am/base/

RUN ln -s /configs/accounts-svc-config /usr/local/am/config.json 

WORKDIR /usr/local/am

CMD am-svc config.json
EXPOSE 8080

# 283MB

