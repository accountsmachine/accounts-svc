
VERSION=$(shell git describe | sed 's/^v//')

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

PROJECT=accounts-machine-${KIND}
SERVICE_ACCOUNT=accounts-svc
SERVICE_ACCOUNT_FULL=${SERVICE_ACCOUNT}@${PROJECT}.iam.gserviceaccount.com
CONFIG=${PROJECT}
ACCOUNT=mark@accountsmachine.io

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

SECRET=accounts-svc-config

GCLOUD_OPTS=\
    --configuration=${CONFIG} \
    --project=${PROJECT}

create-service-account:
	gcloud ${GCLOUD_OPTS} iam service-accounts create \
	    --description 'Accounts service' \
	    --display-name 'Accounts service' \
	    accounts-svc

# This creates a secret key for the service account, and writes it to a secret.
# A bit messy.  It deletes existing service account keys, one of which is
# system generated, which generates an error which is then ignored.  It works,
# but messy.  FIXME.  We don't really need a secret key for the account, keys
# are generated inside Cloud Run containers for this user.  However,
# the application default key management takes 10 seconds to run.  Just putting
# a secret key and loading that is instantaneous start.
create-secret-key:
	-gcloud ${GCLOUD_OPTS} secrets delete --quiet accounts-svc-key
	-keys=$$(gcloud ${GCLOUD_OPTS} iam service-accounts keys list \
	    --format='value(name)' \
	    --iam-account=${SERVICE_ACCOUNT_FULL}) && \
	for v in $${keys}; do \
	    gcloud ${GCLOUD_OPTS} iam service-accounts keys delete $${v} \
	        --iam-account=${SERVICE_ACCOUNT_FULL} --quiet; \
	done
	gcloud ${GCLOUD_OPTS} iam service-accounts keys create \
	    --iam-account=${SERVICE_ACCOUNT_FULL} \
	    private.${KIND}.key.tmp
	gcloud ${GCLOUD_OPTS} secrets create accounts-svc-key \
	    --data-file=private.${KIND}.key.tmp
	gcloud ${GCLOUD_OPTS} secrets get-iam-policy accounts-svc-key \
	    > secret-policy.${KIND}.key.tmp
	sed 's/@@SERVICEACCOUNT@@/${SERVICE_ACCOUNT_FULL}/' secret-policy.json >> secret-policy.${KIND}.key.tmp
	gcloud ${GCLOUD_OPTS} secrets set-iam-policy accounts-svc-key secret-policy.${KIND}.key.tmp
	-rm -f private.${KIND}.key.tmp

# FIXME: Can't run two in parallel.
create-secret-config:
	-gcloud ${GCLOUD_OPTS} secrets delete --quiet accounts-svc-config
	gcloud ${GCLOUD_OPTS} secrets create ${SECRET} \
	    --data-file=config-${KIND}.json
	gcloud ${GCLOUD_OPTS} secrets get-iam-policy ${SECRET} \
	    > secret-policy.${KIND}.tmp
	sed 's/@@SERVICEACCOUNT@@/${SERVICE_ACCOUNT_FULL}/' secret-policy.json >> secret-policy.${KIND}.tmp
	gcloud ${GCLOUD_OPTS} secrets set-iam-policy ${SECRET} secret-policy.${KIND}.tmp

delete-secret:
	gcloud secrets delete --quiet accounts-svc-config

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
	podman run -d --name ${NAME} \
	    -p 8081:8080 \
	    ${CONTAINER}:${VERSION}

stop:
	podman rm -f ${NAME}

clean:
	rm -rf wheels/

SERVICE=accounts-svc
REGION=europe-west1
TAG=v$(subst .,-,${VERSION})
DOMAIN=api.${KIND}.accountsmachine.io

run-list:
	gcloud \
	    --configuration=${CONFIG} \
	    --project ${PROJECT} \
	    run services list

gcloud-setup:
	-gcloud config configurations delete ${CONFIG}
	gcloud config configurations create ${CONFIG} \
	    --account ${ACCOUNT} --project ${PROJECT}
	gcloud --configuration=${CONFIG} auth login 

run-deploy:
	gcloud \
	    ${GCLOUD_OPTS} \
	    run deploy ${SERVICE} \
	    --image=${CONTAINER}:${VERSION} \
	    --allow-unauthenticated \
	    --service-account=${SERVICE_ACCOUNT_FULL} \
	    --concurrency=80 \
	    --cpu=1 \
	    --memory=256Mi \
	    --min-instances=0 \
	    --max-instances=1 \
	    --set-secrets=/configs/accounts-svc-config=accounts-svc-config:latest,/keys/accounts-svc-key=accounts-svc-key:latest \
	    --region=${REGION}

run-domain:
	gcloud \
	    ${GCLOUD_OPTS} \
	    beta run domain-mappings create \
	        --service=${SERVICE} \
		--domain=${DOMAIN} \
	        --region=${REGION}

run-upgrade:
	gcloud run services update ${SERVICE} \
	    --project ${PROJECT} --region ${REGION} \
	    --image ${CONTAINER}:${VERSION} \
	    --set-secrets=/configs/accounts-svc-config=accounts-svc-config:latest,/keys/accounts-svc-key=accounts-svc-key:latest \
	    --update-labels version=${TAG}
