
FROM fedora:35

# FIXME: Clean
RUN dnf update -y && dnf install -y python3-pip

RUN pip3 install ixbrl-reporter

#RUN mkdir /usr/local/ixbrl-reporter-jsonnet

ADD ixbrl-reporter-jsonnet /usr/local/
ADD base /usr/local/

RUN dnf install -y python3-pyOpenSSL python3-ldap python3-jwt

RUN mkdir /root/wheels/
ADD wheels/* /root/wheels/

RUN pip3 install /root/wheels/jsonnet-*
RUN pip3 install /root/wheels/accounts_svc-*

RUN dnf clean all
RUN rm -rf /root/wheels

ADD config-local.json /usr/local/config.json

WORKDIR /usr/local
CMD am-svc config.json
EXPOSE 8081

