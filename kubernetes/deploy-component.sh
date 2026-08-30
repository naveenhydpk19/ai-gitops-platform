#!/bin/bash


if [ -z "$1" ]; then
    printf "Usage: \nArg1: Component \nArg2: Command -> apply or delete\n"
    exit -1
fi
COMPONENT=$1

if [ -z "$2" ]; then
    CMD="apply"
else
    CMD=$2
fi

REGISTRY_HOST=asia.gcr.io
REVISION_ID=latest

PROJECT_NAME=$(gcloud config get-value project)
REGISTRY_PATH="${REGISTRY_HOST}/${PROJECT_NAME}/ntw"
#REGISTRY_PATH="ntw"
IMAGE_PULL_POLICY=IfNotPresent

echo "Image registry path is set to: $REGISTRY_PATH"

cd ./config

echo "-- $CMD $COMPONENT --"
sed 's#IMAGE_REGISTRY_PATH#'${REGISTRY_PATH}'#g' ${COMPONENT}.yaml \
    | sed 's#IMAGE_PULL_POLICY#'${IMAGE_PULL_POLICY}'#g' \
    | sed 's#REVISION_ID#'${REVISION_ID}'#g' \
    | kubectl ${CMD} -f -
