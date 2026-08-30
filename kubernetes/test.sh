#!/bin/bash
echo "---> ${GATEWAY_SVC_ORIGIN}" 
if [ -n "$1" ]; then
    GATEWAY_SVC_ORIGIN="$1"
elif [ -n "${GATEWAY_SVC_ORIGIN}" ]; then
    echo "" > /dev/null
else
    GATEWAY_SVC_ORIGIN="localhost:8080"
fi

echo "Gateway Service origin is set to ${GATEWAY_SVC_ORIGIN}"

USER_NAME=admin
USER_PASS=password
AUTH_CLIENT_CRED=$(printf "web-client:secret" | base64 - )

echo -e '\n--------Get Token----------\n'

curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -H "Authorization: Basic ${AUTH_CLIENT_CRED}" -D - --data 'grant_type=password&username='${USER_NAME}'&password='${USER_PASS} http://${GATEWAY_SVC_ORIGIN}/auth/token

ACCESS_TOKEN=$(curl -s -X POST -H "Authorization: Basic ${AUTH_CLIENT_CRED}" -H "Content-Type: application/x-www-form-urlencoded" --data 'grant_type=password&username='${USER_NAME}'&password='${USER_PASS} http://${GATEWAY_SVC_ORIGIN}/auth/token | jq .access_token | tr -d '"')

echo -e '\n---------Get User Auth---------\n'

curl -X GET -H "Authorization: Bearer $ACCESS_TOKEN" -D - http://${GATEWAY_SVC_ORIGIN}/auth/token/user?access_token=${ACCESS_TOKEN}


echo -e '\n-------Add Products-----------\n'

curl -X PUT -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" --data '{"id":"product-1","name":"Product One","price":10.0}' -D - http://${GATEWAY_SVC_ORIGIN}/products/product-1
echo
curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" --data '' -D - "http://${GATEWAY_SVC_ORIGIN}/products?id=product-2&name=Product%20Two&price=20.0"


echo -e '\n-------Get Products-----------\n'

curl -X GET -H "Authorization: Bearer $ACCESS_TOKEN" -D - http://${GATEWAY_SVC_ORIGIN}/products


echo -e '\n-------Get Product-----------\n'

curl -X GET -H "Authorization: Bearer $ACCESS_TOKEN" -D - http://${GATEWAY_SVC_ORIGIN}/products/product-1


echo -e '\n-------Add Inventory-----------\n'

PROD1QTY=$(curl -s -X GET -H "Authorization: Bearer $ACCESS_TOKEN" http://${GATEWAY_SVC_ORIGIN}/inventory/product-1 | jq .quantity)
if [ "$PROD1QTY" -gt 100 ]; then
    echo -e "Inventory for product-1 already = $PROD1QTY. Not adding."
else
    curl -X PUT -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" --data '{"productId":"product-1","quantity":1000}' -D - http://${GATEWAY_SVC_ORIGIN}/inventory/product-1
fi

echo

PROD2QTY=$(curl -s -X GET -H "Authorization: Bearer $ACCESS_TOKEN" http://${GATEWAY_SVC_ORIGIN}/inventory/product-2 | jq .quantity)
if [ "$PROD2QTY" -gt 100 ]; then
    echo -e "Inventory for product-2 already = $PROD2QTY. Not adding."
else
    curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" --data '' -D - "http://${GATEWAY_SVC_ORIGIN}/inventory?productId=product-2&quantity=5000"
fi

echo -e '\n-------Get All Inventory-----------\n'

curl -X GET -H "Authorization: Bearer $ACCESS_TOKEN" -D - http://${GATEWAY_SVC_ORIGIN}/inventory


echo -e '\n-------Post Add to Cart-----------\n'

curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/x-www-form-urlencoded" --data '' -D - "http://${GATEWAY_SVC_ORIGIN}/carts?id=cart-1&productId=product-1&quantity=1"
echo
curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/x-www-form-urlencoded" --data '' -D - "http://${GATEWAY_SVC_ORIGIN}/carts?id=cart-1&productId=product-2&quantity=2"

echo -e '\n-------Get Cart-----------\n'

curl -X GET -H "Authorization: Bearer $ACCESS_TOKEN" -D - http://${GATEWAY_SVC_ORIGIN}/carts/cart-1


echo -e '\n-------Create Order-----------\n'

curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" --data '' -D - http://${GATEWAY_SVC_ORIGIN}/orders/order/carts/cart-1


echo -e '\n-------Get Orders-----------\n'

curl -X GET -H "Authorization: Bearer $ACCESS_TOKEN" -D - http://${GATEWAY_SVC_ORIGIN}/orders

echo -e '\n-------Get All Inventory-----------\n'

curl -X GET -H "Authorization: Bearer $ACCESS_TOKEN" -D - http://${GATEWAY_SVC_ORIGIN}/inventory

echo -e '\n---------Done---------\n'
