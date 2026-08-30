#!/bin/bash

JAR_FILES="auth common discovery gateway inventory order product"

for JAR_FILE in $JAR_FILES
do
    echo Downloading $JAR_FILE.jar
    curl https://ntw-shared-data.s3.ap-south-1.amazonaws.com/samples/micro-services/$JAR_FILE.jar -o $JAR_FILE.jar
done

echo "-- Done --"
