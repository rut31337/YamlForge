#!/bin/bash

# YamlForge Vulture Analysis Script
# This script runs Vulture with all the learned ignore patterns to find truly unused code

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 YamlForge Vulture Analysis${NC}"
echo "=================================="

# Check if vulture is installed
if ! command -v vulture &> /dev/null; then
    echo -e "${RED}❌ Vulture is not installed. Please install it with:${NC}"
    echo "   pip install vulture"
    exit 1
fi

# Comprehensive ignore list based on our cleanup experience
IGNORE_LIST="__init__,main,setup,test_,_test,conftest,generate_aws_vm,generate_aws_security_group,generate_aws_networking,generate_azure_vm,generate_azure_security_group,generate_azure_networking,generate_gcp_vm,generate_gcp_firewall_rules,generate_ibm_vpc_vm,generate_ibm_security_group,generate_ibm_classic_vm,generate_oci_vm,generate_oci_security_group,generate_alibaba_vm,generate_alibaba_security_group,generate_alibaba_networking,generate_vmware_vm,get_aws_credentials,get_azure_credentials,get_gcp_credentials,get_ibm_vpc_credentials,get_ibm_classic_credentials,get_oci_credentials,get_alibaba_credentials,get_vmware_credentials,get_cert_manager_credentials,oci_config,alibaba_config,validate_openshift_version,create_rosa_account_roles_via_cli,generate_rosa_operator_roles,generate_rosa_oidc_config,generate_rosa_sts_data_sources,generate_lifecycle_management,generate_blue_green_automation,generate_upgrade_automation,generate_ingress_resources,generate_external_dns,generate_gitops_operator,generate_pipelines_operator,generate_serverless_operator,generate_logging_operator,generate_monitoring_operator,generate_storage_operator,generate_service_mesh_operator,generate_metallb_operator,generate_submariner_operator,generate_cert_manager_operator,generate_oadp_operator,ROSAVersionManager,retry_with_backoff,AlibabaImageResolver,GCPImageResolver,OCIImageResolver,GitOpsOperator,PipelinesOperator,ServerlessOperator"

echo -e "${YELLOW}📋 Running Vulture with ignore patterns...${NC}"
echo "   Ignoring: $IGNORE_LIST"
echo ""

# Run vulture
if vulture yamlforge/ --ignore-names "$IGNORE_LIST" --min-confidence 60; then
    echo ""
    echo -e "${GREEN}✅ Vulture analysis completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}📊 Summary:${NC}"
    echo "   • No unused code found, or all findings are false positives"
    echo "   • Codebase is clean and well-maintained"
    echo ""
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo "   • Use --min-confidence 80 for stricter analysis"
    echo "   • Add new ignore patterns to .vulture file"
    echo "   • Review findings manually before removing code"
else
    echo ""
    echo -e "${YELLOW}⚠️  Vulture found potential unused code${NC}"
    echo ""
    echo -e "${BLUE}📋 Next steps:${NC}"
    echo "   1. Review the findings above"
    echo "   2. Verify they are truly unused (not dynamically called)"
    echo "   3. Add false positives to .vulture file"
    echo "   4. Remove confirmed unused code"
    echo ""
    echo -e "${YELLOW}💡 To ignore specific findings, add them to .vulture:${NC}"
    echo "   # Add method names to ignore"
    echo "   method_name"
    echo "   another_method"
fi

echo ""
echo -e "${BLUE}🔧 Usage:${NC}"
echo "   ./tools/run_vulture.sh                    # Run with current settings"
echo "   vulture yamlforge/ --min-confidence 80    # Run with higher confidence"
echo "   vulture yamlforge/ --ignore-names 'pattern1,pattern2'  # Custom ignore" 