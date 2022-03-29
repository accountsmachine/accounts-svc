
VERSION=0.0.2

JSONNET_REPO=git@github.com:cybermaggedon/ixbrl-reporter-jsonnet
#REPORTER_REPO=https://github.com/cybermaggedon/ixbrl-reporter

all: ixbrl-reporter-jsonnet wheels

ixbrl-reporter-jsonnet:
	(mkdir $@; cd $@; git clone ${JSONNET_REPO} .)

NAME=accounts-svc
REPO=europe-west2-docker.pkg.dev/accounts-machine-dev/accounts-machine
CONTAINER=${REPO}/${NAME}

container: all
	podman build -f Containerfile -t ${CONTAINER}:${VERSION} \
	    --format docker

login:
	gcloud auth print-access-token | \
	    podman login -u oauth2accesstoken --password-stdin \
	        europe-west2-docker.pkg.dev

wheels: setup.py
	rm -rf wheels && mkdir wheels
	pip3 wheel -w wheels --no-deps .
	pip3 wheel -w wheels --no-deps jsonnet
	pip3 wheel -w wheels --no-deps gnucash-uk-vat
	pip3 wheel -w wheels --no-deps ixbrl-reporter
	pip3 wheel -w wheels --no-deps ixbrl-parse

push:
	podman push --remove-signatures ${CONTAINER}:${VERSION}

start:
	podman run -d --name ${NAME} \
	    -p 8081:8081 \
	    ${CONTAINER}:${VERSION}

stop:
	podman rm -f ${NAME}

clean:
	rm -rf wheels/

