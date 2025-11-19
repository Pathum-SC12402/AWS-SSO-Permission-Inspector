Here is your **final, clean, ready-to-use `README.md`** exactly in the format you asked for.

---

# **AWS IAM & Identity Center (IC) Report Generator**

This tool generates a complete IAM + AWS Identity Center report for multiple AWS accounts and exports the results into an Excel file.
It combines AWS SSO data, IAM data, and data from a local CSV file named **`AWS Account Owners.csv`**.

---

## **1. Clone the Repository**

```bash
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>
```

---

## **2. Install Python Dependencies**

Run the following:

```bash
python -m pip install boto3 openpyxl
```

This installs:

* `boto3` → AWS SDK for Python
* `openpyxl` → Excel file handling

---

## **3. Configure AWS Credentials**

You must configure AWS credentials for the **delegated administrator account** or an account that has permission to query IAM Identity Center.

### **Option A: Default profile**

```bash
aws configure
```

### **Option B: Named profile**

```bash
aws configure --profile delegated
```

### **Option C: If assuming a role**

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::<account-id>:role/<delegated-role> \
  --role-session-name ic-report-session
```

---

## **4. Prepare the CSV Input File**

Your account metadata file **must** be named:

```
AWS Account Owners.csv
```

It must be in the **same directory** as `iam_ic_report.py`.

### **Required Columns**

| Column Name   | Meaning                                   |
| ------------- | ----------------------------------------- |
| Account No    | AWS Account Number (12 digits)            |
| Account ID    | Account Name (ex: Production-1 / Dev-App) |
| Account Owner | Owner Name or Email                       |
| Account Type  | Environment type (ex: Prod, Dev, QA)      |

### **Example CSV**

```
Account No,Account ID,Account Owner,Account Type
007952453283,Dev-App,Venura Ubayathilakarachchi,Development
072308801333,BAU-Analyst,Janaka M. Perera,Production
```

---

## **5. Run the Script**

Execute:

```bash
py iam_ic_report.py
```

or on Linux/macOS:

```bash
python3 iam_ic_report.py
```

You will be prompted:

```
Enter Account IDs separated by commas (Example: 111111111111,222222222222)
AWS Account IDs:
```

Example input:

```
007952453283,072308801333
```

---

## **6. What the Script Does**

The script:

1. Loads account details from **AWS Account Owners.csv**
2. Connects to AWS Identity Center (SSO)
3. Pulls:

   * Permission Sets
   * AWS Managed Policies
   * Customer Managed Policies
   * Inline Policy JSON
   * User → Group → Permission Set mappings
4. Combines everything into a single structured dataset
5. Generates an Excel file:

```
IAM_IC_Report.xlsx
```

---

## **7. Output Excel Format**

The file contains:

* Account No
* Account ID
* Account Owner
* Account Type
* Principal ID
* Principal Type
* Group/User Name
* Users in Group / Direct User
* Permission Set Name
* AWS Managed Policies
* Customer Managed Policies
* Inline Policy JSON

---

## **8. Notes**

* `AWS Account Owners.csv` **must remain in the script directory**
* Do not rename columns; header names must match exactly
* Ensure your AWS IAM role has permissions:

```
sso:*
identitystore:*
iam:GetPolicy
iam:GetPolicyVersion
```
