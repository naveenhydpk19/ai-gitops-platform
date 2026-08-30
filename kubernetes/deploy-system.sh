#!/bin/bash

if [ -z "$1" ]; then
    CMD="apply"
else
    CMD=$1
fi

REGISTRY_HOST=asia.gcr.io
REVISION_ID=latest

PROJECT_NAME=$(gcloud config get-value project)
IMAGE_REGISTRY_PATH="${REGISTRY_HOST}/${PROJECT_NAME}/ntw"
#IMAGE_REGISTRY_PATH="ntw"
IMAGE_PULL_POLICY=IfNotPresent

echo "Image registry path is set to: $REGISTRY_PATH"

declare -a arr=("config-map" "cassandra" "gateway-svc" \
		"auth-svc" "product-svc" "order-svc" "inventory-svc")

cd ./config
for COMPONENT in "${arr[@]}"
do

    echo "-- $CMD $COMPONENT --"
    sed 's#IMAGE_REGISTRY_PATH#'${IMAGE_REGISTRY_PATH}'#g' ${COMPONENT}.yaml \
	| sed 's#IMAGE_PULL_POLICY#'${IMAGE_PULL_POLICY}'#g' \
	| sed 's#REVISION_ID#'${REVISION_ID}'#g' \
	| kubectl $CMD -f -

done
