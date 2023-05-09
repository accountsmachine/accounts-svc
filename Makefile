
VERSION=$(shell git describe | sed 's/^v//')

JSONNET_REPO=https://github.com/cybermaggedon/ixbrl-reporter-jsonnet
JSONNET_VERSION=v1.0.3

#REPORTER_REPO=https://github.com/cybermaggedon/ixbrl-reporter

all: ixbrl-reporter-jsonnet wheels

ixbrl-reporter-jsonnet:
	( \
	  mkdir $@ && \
	  cd $@ && \
	  git clone ${JSONNET_REPO} . && \
	  git checkout ${JSONNET_VERSION} \
	)

KIND=dev
NAME=accounts-svc

CONTAINER=accounts-svc

container-dev: KIND=dev
container-dev: container

container-stage: KIND=stage
container-stage: container

container-prod: KIND=prod
container-prod: container

create-secret-dev: KIND=dev
create-secret-dev: create-secret

everything:
	make everything-dev
	make everything-stage
	make everything-prod

everything-dev:
	rm -rf wheels && make wheels
	make container-dev
	make push-dev
	make run-upgrade KIND=dev

everything-stage:
	rm -rf wheels && make wheels
	make container-stage
	make push-stage
	make run-upgrade KIND=stage

everything-prod:
	rm -rf wheels && make wheels
	make container-prod
	make push-prod
	make run-upgrade KIND=prod

container: dep-wheels wheels
	podman build -f Containerfile -t ${CONTAINER}:${VERSION} \
	    --format docker

login:
	gcloud auth print-access-token | \
	    podman login -u oauth2accesstoken --password-stdin \
	        europe-west2-docker.pkg.dev

dep-wheels:
	rm -rf $@ && mkdir $@
	pip3 wheel -w $@ --no-deps jsonnet
	pip3 wheel -w $@ --no-deps gnucash-uk-vat
	pip3 wheel -w $@ --no-deps ixbrl-reporter
	pip3 wheel -w $@ --no-deps ixbrl-parse

wheels: setup.py scripts/am-svc $(wildcard */*.py)
	rm -rf $@ && mkdir $@
	env PACKAGE_VERSION=${VERSION} pip3 wheel -w $@ --no-deps .

push:
	podman push --remove-signatures ${CONTAINER}:${VERSION}

start:
	podman run -i -t --name ${NAME} \
	    -i -t \
	    -p 8081:8081 \
	    -v $$(pwd)/keys:/keys \
	    -v $$(pwd)/configs:/configs \
	    ${CONTAINER}:${VERSION}

stop:
	podman rm -f ${NAME}

clean:
	rm -rf wheels/
