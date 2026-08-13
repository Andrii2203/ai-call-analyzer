#!/bin/bash
awslocal s3 mb s3://sales-score-dev

awslocal dynamodb create-table \
    --table-name SalesScores \
    --key-schema \
        AttributeName=PK,KeyType=HASH \
        AttributeName=SK,KeyType=RANGE \
    --attribute-definitions \
        AttributeName=PK,AttributeType=S \
        AttributeName=SK,AttributeType=S \
    --billing-mode PAY_PER_REQUEST

echo "LocalStack initialized: S3 bucket 'sales-score-dev' and DynamoDB table 'SalesScores' created."
