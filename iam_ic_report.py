import boto3
from openpyxl import Workbook
from botocore.exceptions import ClientError
import json # Import json for better inline policy formatting

# ------------------------------------------------------
# Initialize AWS Clients
# ------------------------------------------------------
# NOTE: Ensure your AWS region is correct. The original was 'ap-southeast-1'.
# If you are in another region, change this value.
REGION = "ap-southeast-1"
sso = boto3.client("sso-admin", region_name=REGION)
identity = boto3.client("identitystore", region_name=REGION)

# ------------------------------------------------------
# Auto-discover Identity Center Instance
# ------------------------------------------------------
def get_sso_details():
    """Finds the ARN and ID of the first available Identity Center instance."""
    try:
        instances = sso.list_instances()["Instances"]
        if not instances:
            raise Exception("No AWS IAM Identity Center instance found in the specified region!")
        inst = instances[0]
        return inst["InstanceArn"], inst["IdentityStoreId"]
    except ClientError as e:
        print(f"AWS Client Error during SSO instance lookup: {e}")
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise

try:
    instance_arn, identity_store_id = get_sso_details()
except Exception:
    exit(1)

# ------------------------------------------------------
# Enter Multiple Account IDs
# ------------------------------------------------------
print("Enter Account IDs separated by commas (Example: 111111111111,222222222222)")
account_ids = [a.strip() for a in input("AWS Account IDs: ").split(",") if a.strip()]
if not account_ids:
    print("No account IDs provided. Exiting.")
    exit(1)

# ------------------------------------------------------
# Get Permission Sets for Account
# ------------------------------------------------------
def get_permission_sets_for_account(account_id):
    """Lists all permission sets provisioned to a specific account."""
    permission_sets = []
    next_token = None
    try:
        while True:
            params = {"InstanceArn": instance_arn, "AccountId": account_id}
            if next_token:
                params["NextToken"] = next_token
            resp = sso.list_permission_sets_provisioned_to_account(**params)
            permission_sets.extend(resp["PermissionSets"])
            next_token = resp.get("NextToken")
            if not next_token:
                break
    except ClientError as e:
        print(f"Error listing permission sets for account {account_id}: {e}")
    return permission_sets

# ------------------------------------------------------
# Helper → Get Group Name
# ------------------------------------------------------
def get_group_name(group_id):
    """Retrieves the DisplayName of a group from Identity Store."""
    try:
        resp = identity.describe_group(IdentityStoreId=identity_store_id, GroupId=group_id)
        return resp.get("DisplayName", "")
    except identity.exceptions.ResourceNotFoundException:
        return f"Group ID Not Found: {group_id}"
    except Exception:
        return "Unknown"

# ------------------------------------------------------
# Helper → Get Users in Group (Safe)
# ------------------------------------------------------
def get_users_of_group(group_id):
    """Retrieves the display names of all users in a group."""
    users = []
    # Pre-validation (as in original script)
    try:
        identity.describe_group(IdentityStoreId=identity_store_id, GroupId=group_id)
    except identity.exceptions.ResourceNotFoundException:
        print(f"❌ Group not found: {group_id} — skipping")
        return []
    except Exception as e:
        print(f"❌ Error validating group {group_id}: {e}")
        return []

    memberships = []
    next_token = None
    try:
        while True:
            params = {"IdentityStoreId": identity_store_id, "GroupId": group_id}
            if next_token:
                params["NextToken"] = next_token
            resp = identity.list_group_memberships(**params)
            memberships.extend(resp.get("GroupMemberships", []))
            next_token = resp.get("NextToken")
            if not next_token:
                break
    except ClientError as e:
        print(f"Error listing group memberships for {group_id}: {e}")

    for m in memberships:
        user_id = m["MemberId"]["UserId"]
        try:
            u = identity.describe_user(IdentityStoreId=identity_store_id, UserId=user_id)
            name = u.get("DisplayName") or u.get("UserName") or "Unknown"
        except:
            name = "Unknown"
        users.append(name)
    return users

# ------------------------------------------------------
# Excel Setup
# ------------------------------------------------------
wb = Workbook()
ws = wb.active
ws.title = "SSO Report"

# Excel Header Row
ws.append([
    "Account ID",
    "Principal ID",
    "Principal Type",
    "Group/User Name",
    "Users in Group / Direct User",
    "Permission Set Name",
    "AWS Managed Policies",
    "Customer Managed Policies",
    "Inline Policy JSON"
])

# ------------------------------------------------------
# Main Logic
# ------------------------------------------------------
for account_id in account_ids:
    print(f"\n🔍 Processing Account: {account_id}")

    permission_sets = get_permission_sets_for_account(account_id)
    if not permission_sets:
        print(f"⚠️ No permission sets found for account {account_id}")
        continue

    for ps_arn in permission_sets:
        
        # --- Permission Set Details ---
        try:
            ps_details = sso.describe_permission_set(InstanceArn=instance_arn, PermissionSetArn=ps_arn)["PermissionSet"]
            ps_name = ps_details["Name"]
            print(f"  - Permission Set: {ps_name}")
        except ClientError as e:
            print(f"Error describing permission set {ps_arn}: {e}")
            continue

        # --- Managed Policies (AWS and Customer by ARN) ---
        aws_managed = []
        customer_managed_names = [] # This list will hold both ARN-attached and Reference-attached policy names
        next_token = None
        
        # 1. Policies attached by ARN (AWS or Customer Managed)
        while True:
            params = {"InstanceArn": instance_arn, "PermissionSetArn": ps_arn}
            if next_token:
                params["NextToken"] = next_token

            resp = sso.list_managed_policies_in_permission_set(**params)

            for policy in resp.get("AttachedManagedPolicies", []):
                arn = policy.get("Arn", "")
                name = policy.get("Name", "Unknown")

                if arn.startswith("arn:aws:iam::aws:policy"):
                    aws_managed.append(name)
                else:
                    # This captures Customer Managed Policies attached via ARN
                    customer_managed_names.append(name) 

            next_token = resp.get("NextToken")
            if not next_token:
                break
        
        # 2. FIX: Policies attached by Reference (Customer Managed, by Name/Path)
        next_token = None
        while True:
            params = {"InstanceArn": instance_arn, "PermissionSetArn": ps_arn}
            if next_token:
                params["NextToken"] = next_token
            
            # Use the correct API to list Customer Managed Policies referenced by Name/Path
            resp = sso.list_customer_managed_policy_references_in_permission_set(**params)

            for policy_ref in resp.get("CustomerManagedPolicyReferences", []):
                ref_path = policy_ref.get("Path", "")
                ref_name = policy_ref.get("Name", "Unknown")
                
                # Format policy name for readability: Path/Name
                if ref_path and ref_path != '/':
                    # Remove trailing slash if it exists, then combine with name
                    full_name = f"{ref_path.rstrip('/')}/{ref_name}"
                else:
                    # If path is '/' or empty, just use the name
                    full_name = ref_name
                    
                customer_managed_names.append(full_name)


            next_token = resp.get("NextToken")
            if not next_token:
                break


        # --- Inline Policy ---
        try:
            inline_policy = sso.get_inline_policy_for_permission_set(
                InstanceArn=instance_arn,
                PermissionSetArn=ps_arn
            ).get("InlinePolicy", "")
            if inline_policy:
                # Pretty print JSON for better visibility in the Excel cell
                inline_policy = json.dumps(json.loads(inline_policy), indent=2) 
        except ClientError:
            inline_policy = ""

        # --- Account Assignments ---
        assignments = []
        next_token = None
        while True:
            params = {"InstanceArn": instance_arn, "PermissionSetArn": ps_arn, "AccountId": account_id}
            if next_token:
                params["NextToken"] = next_token
            resp = sso.list_account_assignments(**params)
            assignments.extend(resp["AccountAssignments"])
            next_token = resp.get("NextToken")
            if not next_token:
                break

        # --- Write Details for Each Assignment ---
        for a in assignments:
            principal_id = a["PrincipalId"]
            principal_type = a["PrincipalType"]  # GROUP or USER
            
            group_name = ""
            user_list_str = ""

            if principal_type == "GROUP":
                group_name = get_group_name(principal_id)
                group_users = get_users_of_group(principal_id)
                user_list_str = ", ".join(group_users)
                user_or_group_name = group_name
            elif principal_type == "USER":
                try:
                    u = identity.describe_user(IdentityStoreId=identity_store_id, UserId=principal_id)
                    user_name = u.get("DisplayName") or u.get("UserName") or "Unknown"
                except:
                    user_name = "Unknown"
                user_or_group_name = user_name
                user_list_str = user_name # Direct user is the only user

            ws.append([
                account_id,
                principal_id,
                principal_type,
                user_or_group_name,
                user_list_str,
                ps_name,
                ", ".join(aws_managed),
                ", ".join(customer_managed_names),
                inline_policy
            ])

# ------------------------------------------------------
# Save Excel
# ------------------------------------------------------
output = "multi_account_permission_sets_report.xlsx"
try:
    wb.save(output)
    print(f"\n✅ Report generated successfully: {output}")
except Exception as e:
    print(f"\n❌ Failed to save Excel file: {e}")
    print("Please ensure the file is not currently open and try again.")