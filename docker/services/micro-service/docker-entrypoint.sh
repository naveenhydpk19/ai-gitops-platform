#!/bin/bash

if [ -z "$1" ]; then
    echo "**** ERROR: Missing service id argument ****"
    exit -1
else
    if [ "$1" == "bash" ]; then
	exec "/bin/bash"
    fi
    SERVICE_ID=$1
    echo "Running service ${SERVICE_ID}"
fi

if [ -z "${JAVA_HEAP_MEMORY}" ]; then
  JAVA_HEAP_MEMORY=-Xmx512M
fi

JAVA_OPTIONS="$JAVA_HEAP_MEMORY"
JAVA_ARGS="$JAVA_OPTIONS"

echo "Executing Spring Boot with Java Args: $JAVA_ARGS"
java $JAVA_ARGS -jar /usr/jar/${SERVICE_ID}.jar
