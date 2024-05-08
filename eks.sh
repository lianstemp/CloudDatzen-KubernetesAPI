#!/bin/bash

eksctl create cluster --name CloudDatzen-Cluster --version 1.29 --region us-east-1 --nodegroup-name database --node-type t2.small --nodes 1

eksctl utils associate-iam-oidc-provider --region us-east-1 --cluster CloudDatzen-Cluster --approve

eksctl create iamserviceaccount --region us-east-1 --name ebs-csi-controller-sa --namespace kube-system --cluster CloudDatzen-Cluster --role-name AmazonEKS_EBS_CSI_DriverRole --role-only --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy --approve

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
eksctl create addon --name aws-ebs-csi-driver  --region us-east-1 --cluster CloudDatzen-Cluster --service-account-role-arn arn:aws:iam::${ACCOUNT_ID}:role/AmazonEKS_EBS_CSI_DriverRole --force

