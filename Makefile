
VERSION=0.9.1

JSONNET_REPO=git@github.com:cybermaggedon/ixbrl-reporter-jsonnet
#REPORTER_REPO=https://github.com/cybermaggedon/ixbrl-reporter

all: ixbrl-reporter-jsonnet wheels

ixbrl-reporter-jsonnet:
	(mkdir $@; cd $@; git clone ${JSONNET_REPO} .)

ART_REPO=europe-west2-docker.pkg.dev

KIND=dev
NAME=accounts-svc

CONFIG_dev=config-dev.json
CONFIG_stage=config-stage.json
CONFIG_prod=config-prod.json

REPO_dev=${ART_REPO}/accounts-machine-dev/accounts-machine
REPO_stage=${ART_REPO}/accounts-machine-stage/accounts-machine
REPO_prod=${ART_REPO}/accounts-machine-prod/accounts-machine

REPO=${REPO_${KIND}}

CONTAINER=${REPO}/${NAME}

repo:
	echo ${CONTAINER}

container-dev: KIND=dev
container-dev: container

container-stage: KIND=stage
container-stage: container

container-prod: KIND=prod
container-prod: container

push-dev: KIND=dev
push-dev: push

push-stage: KIND=stage
push-stage: push

push-prod: KIND=prod
push-prod: push

create-secret-dev: KIND=dev
create-secret-dev: create-secret

SECRET=accounts-svc-config
USER=accounts-svc@accounts-machine-dev.iam.gserviceaccount.com

create-secret:
	-gcloud secrets delete --quiet accounts-svc-config
	gcloud secrets create ${SECRET} \
	    --data-file=config-${KIND}.json
	gcloud secrets get-iam-policy ${SECRET} > secret-policy.tmp
	cat secret-policy.json >> secret-policy.tmp
	gcloud secrets set-iam-policy ${SECRET} secret-policy.tmp

delete-secret:
	gcloud secrets delete --quiet accounts-svc-config

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
	    -p 8081:8080 \
	    ${CONTAINER}:${VERSION}

stop:
	podman rm -f ${NAME}

clean:
	rm -rf wheels/

SERVICE=accounts-svc
PROJECT=accounts-machine-dev
REGION=europe-west1
TAG=v$(subst .,-,${VERSION})

deploy:
	gcloud run services update ${SERVICE} \
	    --project ${PROJECT} --region ${REGION} \
	    --image ${CONTAINER}:${VERSION} \
	    --tag ${TAG}

