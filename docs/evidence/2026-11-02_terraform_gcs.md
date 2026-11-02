# Terraform: GCS landing bucket and access, 2026-11-02

Project `vayba-elimane-2026` (no Google organization), region `us-west1`, state in `gs://vayba-elimane-2026-tfstate`.
Member e-mail addresses are replaced by `<member>`.

## Final state

```text
$ terraform apply
google_storage_bucket_iam_member.snowflake_read[0]: Creation complete after 6s [id=b/vayba-elimane-2026-landing/projects/vayba-elimane-2026/roles/vaybaSnowflakeReader/serviceAccount:k1qv50000@prod3-f617.iam.gserviceaccount.com]

Apply complete! Resources: 1 added, 0 changed, 0 destroyed.

Outputs:

landing_bucket = "gs://vayba-elimane-2026-landing"
```

Resources declared: landing bucket (private, uniform access, 30-day lifecycle), custom role `vaybaSnowflakeReader`
(`storage.buckets.get`, `storage.objects.get`, `storage.objects.list`), read and write access for `<member>`,
read access for Snowflake's service account.

## Incidents met on the way

1. **Error 412, organization policy.** The first project, created with a school account, belonged to the school's
   Google organization. Granting Snowflake's service account failed:
   `Error 412: One or more users named in the policy do not belong to a permitted customer`.
   Diagnosis: `gcloud resource-manager org-policies describe iam.allowedPolicyMemberDomains --project=<old project> --effective`
   showed only the school's customer id. Fix: a new project with no organization, same Terraform code.
2. **Error 400, IAM propagation.** On the new project, the first apply created the custom role, then failed to use it
   two seconds later: `Role (projects/vayba-elimane-2026/roles/vaybaSnowflakeReader) does not exist in the resource's hierarchy`.
   Fix: apply again a minute later; Terraform only added the missing binding (output above).
3. **Bucket moved, permissions lost.** Moving the first bucket from `europe-west9` to `us-west1` replaced it; its
   permissions disappeared with it although the first plan did not list them. Lesson: run `terraform plan` after
   every apply and expect `No changes`.
