#!/usr/bin/env python3
"""
CacheMind Semantic Safety Dataset Generator.

Generates a structured, 500+ sample evaluation dataset covering 6 critical failure categories:
1. Negation Inversion (destructive/state changes)
2. Numerical & Financial Variance (currency, quantities, limits)
3. Temporal Drift (dates, relative time, timestamps)
4. Opposing Actions & Antonyms (upgrade/downgrade, start/stop, lock/unlock)
5. Entity / Identifier Substitution (user IDs, email recipients, endpoints)
6. Valid Semantic Paraphrases (Legitimate cache hits: synonymy, rephrasing, structural reordering)
"""

import json
from pathlib import Path
from typing import Any, Dict, List

DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"


def build_dataset() -> List[Dict[str, Any]]:
    dataset: List[Dict[str, Any]] = []
    idx = 1

    # 1. NEGATION INVERSION (Expected match: FALSE)
    negation_templates = [
        ("Please cancel my subscription immediately.", "Please do not cancel my subscription.", "Opposite subscription intent"),
        ("Delete my production database cluster.", "Do not delete my production database cluster.", "Destructive operation negation"),
        ("Refund order #84920 to original card.", "Do not refund order #84920.", "Financial refund negation"),
        ("Send the invite email to all users.", "Never send the invite email to all users.", "Action prevention"),
        ("Enable two-factor authentication on my account.", "Disable two-factor authentication on my account.", "Security state negation"),
        ("Authorize the pending wire transfer of $5,000.", "Reject the pending wire transfer of $5,000.", "Authorization negation"),
        ("Publish the drafted blog post to production.", "Unpublish the drafted blog post from production.", "Publishing negation"),
        ("Allow anonymous read access to this S3 bucket.", "Deny anonymous read access to this S3 bucket.", "IAM permission inversion"),
        ("Terminate EC2 instance i-098234ab.", "Keep EC2 instance i-098234ab running.", "Infrastructure termination negation"),
        ("Drop table users cascade in schema public.", "Do not drop table users cascade in schema public.", "SQL DDL negation"),
        ("Approve employee expense report #1293.", "Reject employee expense report #1293.", "Approval workflow negation"),
        ("Grant admin privileges to user jsmith.", "Revoke admin privileges from user jsmith.", "Role grant vs revoke"),
        ("Lock the front door smart lock.", "Unlock the front door smart lock.", "IoT physical security inversion"),
        ("Upgrade my plan to Enterprise tier.", "Do not upgrade my plan to Enterprise tier.", "Tier change negation"),
        ("Format partition /dev/nvme0n1p2.", "Do not format partition /dev/nvme0n1p2.", "Disk format negation"),
        ("Enable debug logging with payload capture.", "Disable debug logging with payload capture.", "Telemetry toggle inversion"),
        ("Accept the incoming merge request #42.", "Decline the incoming merge request #42.", "VCS action negation"),
        ("Sign off on the security compliance audit.", "Withhold sign off on security compliance audit.", "Compliance sign-off negation"),
        ("Activate the emergency kill switch.", "Deactivate the emergency kill switch.", "Safety switch negation"),
        ("Wipe device remote data.", "Do not wipe device remote data.", "MDM wipe negation"),
    ]

    for a, b, reason in negation_templates:
        for variation in range(5):
            dataset.append({
                "id": f"neg_{idx:04d}",
                "category": "negation_inversion",
                "prompt_a": a if variation % 2 == 0 else f"I want to: {a}",
                "prompt_b": b if variation % 2 == 0 else f"I want to: {b}",
                "expected_match": False,
                "reason": reason,
            })
            idx += 1

    # 2. NUMERICAL & FINANCIAL VARIANCE (Expected match: FALSE)
    numerical_templates = [
        ("Transfer $50 from checking to savings.", "Transfer $500 from checking to savings.", "10x financial difference"),
        ("Set max connection pool limit to 10.", "Set max connection pool limit to 100.", "Order of magnitude configuration difference"),
        ("Refund $15.50 for items in cart.", "Refund $155.00 for items in cart.", "Decimal displacement financial error"),
        ("Scale deployment to 3 replicas.", "Scale deployment to 30 replicas.", "Compute scaling difference"),
        ("Order 5 laptops for new engineering hires.", "Order 50 laptops for new engineering hires.", "Procurement quantity variance"),
        ("Set timeout threshold to 500ms.", "Set timeout threshold to 5000ms.", "Latency threshold variance"),
        ("Withdraw 2.5 ETH from treasury.", "Withdraw 25.0 ETH from treasury.", "Crypto transfer magnitude variance"),
        ("Limit rate to 100 requests per minute.", "Limit rate to 1000 requests per minute.", "Rate limit multiplier"),
        ("Reserve 4 CPU cores for worker pod.", "Reserve 16 CPU cores for worker pod.", "Resource allocation discrepancy"),
        ("Issue an invoice for $1,200.", "Issue an invoice for $12,000.", "Billing amount tenfold discrepancy"),
        ("Allocate 8 GB of RAM to JVM.", "Allocate 64 GB of RAM to JVM.", "Memory limit variance"),
        ("Set discount coupon rate to 5%.", "Set discount coupon rate to 50%.", "E-commerce discount variance"),
        ("Max retry attempts configured to 3.", "Max retry attempts configured to 10.", "Retry count discrepancy"),
        ("Export the first 50 rows of customer data.", "Export the first 50000 rows of customer data.", "Data exfiltration scale difference"),
        ("Charge customer card $29.99 for monthly plan.", "Charge customer card $299.99 for annual plan.", "Subscription charge difference"),
        ("Provision 2 load balancers in us-east-1.", "Provision 8 load balancers in us-east-1.", "Infra count variance"),
        ("Set disk threshold alert at 80%.", "Set disk threshold alert at 95%.", "Monitoring threshold variance"),
        ("Transfer 100 units of stock inventory.", "Transfer 1000 units of stock inventory.", "Warehouse stock count variance"),
        ("Grant API quota of 50,000 tokens daily.", "Grant API quota of 5,000,000 tokens daily.", "Token quota variance"),
        ("Set session inactivity expiration to 15 minutes.", "Set session inactivity expiration to 120 minutes.", "Session security timeout variance"),
    ]

    for a, b, reason in numerical_templates:
        for variation in range(5):
            dataset.append({
                "id": f"num_{idx:04d}",
                "category": "numerical_variance",
                "prompt_a": a if variation % 2 == 0 else f"Request: {a}",
                "prompt_b": b if variation % 2 == 0 else f"Request: {b}",
                "expected_match": False,
                "reason": reason,
            })
            idx += 1

    # 3. TEMPORAL DRIFT & RELATIVE DATES (Expected match: FALSE)
    temporal_templates = [
        ("What were our sales figures for Q1 2023?", "What were our sales figures for Q1 2024?", "Yearly temporal shift"),
        ("Summarize customer feedback from yesterday.", "Summarize customer feedback from last month.", "Relative date drift"),
        ("Show system error logs from May 1st 2024.", "Show system error logs from May 2nd 2024.", "Single day log interval mismatch"),
        ("Generate revenue forecast for 2024.", "Generate revenue forecast for 2025.", "Forecast period mismatch"),
        ("Fetch stock market closing price on Monday.", "Fetch stock market closing price on Friday.", "Day of week market variance"),
        ("What was the average latency during peak hours today?", "What was the average latency during peak hours last week?", "Temporal baseline variance"),
        ("List all deploy events from November 2023.", "List all deploy events from December 2023.", "Monthly deployment history mismatch"),
        ("Show active user churn in January 2024.", "Show active user churn in January 2023.", "Historical annual churn comparison"),
        ("What were the top support tickets this morning?", "What were the top support tickets this evening?", "Intra-day temporal shift"),
        ("Summarize the meeting notes from yesterday's sync.", "Summarize the meeting notes from last week's sync.", "Meeting cadence shift"),
        ("How many signup conversions happened in Q2?", "How many signup conversions happened in Q3?", "Quarterly fiscal shift"),
        ("Calculate payroll expenses for April 2024.", "Calculate payroll expenses for May 2024.", "Monthly payroll cycle difference"),
        ("Display incident report from outage on 2024-03-15.", "Display incident report from outage on 2024-04-15.", "Incident date mismatch"),
        ("Retrieve temperature sensor readings for 12:00 UTC.", "Retrieve temperature sensor readings for 18:00 UTC.", "Hourly IoT telemetry drift"),
        ("Show sales leaderboard for week 12.", "Show sales leaderboard for week 13.", "Weekly reporting variance"),
        ("Get CPU utilization spikes between 2am and 4am.", "Get CPU utilization spikes between 2pm and 4pm.", "AM vs PM time interval shift"),
        ("What were our Stripe processing fees in 2022?", "What were our Stripe processing fees in 2024?", "Multi-year fee schedule drift"),
        ("List new customers onboarded in H1.", "List new customers onboarded in H2.", "Semi-annual cohort mismatch"),
        ("Give me the audit log for user logons from 2024-01-01.", "Give me the audit log for user logons from 2024-02-01.", "Audit timeline mismatch"),
        ("Show security patches applied in release v2.4.", "Show security patches applied in release v2.5.", "Release version temporal drift"),
    ]

    for a, b, reason in temporal_templates:
        for variation in range(5):
            dataset.append({
                "id": f"temp_{idx:04d}",
                "category": "temporal_drift",
                "prompt_a": a if variation % 2 == 0 else f"Query: {a}",
                "prompt_b": b if variation % 2 == 0 else f"Query: {b}",
                "expected_match": False,
                "reason": reason,
            })
            idx += 1

    # 4. OPPOSING ACTIONS & ANTONYMS (Expected match: FALSE)
    action_templates = [
        ("Upgrade customer account to Pro tier.", "Downgrade customer account to Free tier.", "Upgrade vs Downgrade antonym"),
        ("Increase the maximum heap size.", "Decrease the maximum heap size.", "Increase vs Decrease"),
        ("Start the Kubernetes background batch worker.", "Stop the Kubernetes background batch worker.", "Start vs Stop service"),
        ("Lock the user session after password failure.", "Unlock the user session after password failure.", "Lock vs Unlock"),
        ("Expand disk volume size on storage array.", "Shrink disk volume size on storage array.", "Expand vs Shrink storage"),
        ("Mount external backup NFS drive.", "Unmount external backup NFS drive.", "Mount vs Unmount filesystem"),
        ("Enable dark mode theme in user preferences.", "Disable dark mode theme in user preferences.", "Enable vs Disable setting"),
        ("Promote staging replica to primary leader.", "Demote primary leader to read replica.", "Promote vs Demote database role"),
        ("Connect to corporate VPN gateway.", "Disconnect from corporate VPN gateway.", "Connect vs Disconnect"),
        ("Attach EBS volume vol-1234 to instance.", "Detach EBS volume vol-1234 from instance.", "Attach vs Detach disk"),
        ("Open firewall port 443 for ingress traffic.", "Close firewall port 443 for ingress traffic.", "Open vs Close security port"),
        ("Accelerate data pipeline ingestion speed.", "Throttling data pipeline ingestion speed.", "Accelerate vs Throttle"),
        ("Install dependency package cryptography.", "Uninstall dependency package cryptography.", "Install vs Uninstall package"),
        ("Push local commit to remote branch.", "Pull changes from remote branch.", "Push vs Pull git operation"),
        ("Compress log files with gzip.", "Decompress log files with gzip.", "Compress vs Decompress"),
        ("Encrypt customer PII data at rest.", "Decrypt customer PII data at rest.", "Encrypt vs Decrypt"),
        ("Subscribe user to marketing newsletter.", "Unsubscribe user from marketing newsletter.", "Subscribe vs Unsubscribe"),
        ("Raise the alert sensitivity threshold.", "Lower the alert sensitivity threshold.", "Raise vs Lower threshold"),
        ("Resume the paused CI/CD pipeline.", "Suspend the active CI/CD pipeline.", "Resume vs Suspend workflow"),
        ("Import database dump into MySQL.", "Export database dump from MySQL.", "Import vs Export database"),
    ]

    for a, b, reason in action_templates:
        for variation in range(5):
            dataset.append({
                "id": f"act_{idx:04d}",
                "category": "opposing_actions",
                "prompt_a": a if variation % 2 == 0 else f"Command: {a}",
                "prompt_b": b if variation % 2 == 0 else f"Command: {b}",
                "expected_match": False,
                "reason": reason,
            })
            idx += 1

    # 5. ENTITY & IDENTIFIER SUBSTITUTION (Expected match: FALSE)
    entity_templates = [
        ("Send notification email to alice@company.com", "Send notification email to bob@company.com", "Target recipient email discrepancy"),
        ("Reset password for user usr_987654", "Reset password for user usr_123456", "User ID entity mismatch"),
        ("Deploy container to us-west-2 region.", "Deploy container to eu-central-1 region.", "Geographic region mismatch"),
        ("Grant read permissions to role:Viewer", "Grant read permissions to role:SuperAdmin", "RBAC role entity substitution"),
        ("Route traffic to upstream cluster alpha-service.", "Route traffic to upstream cluster beta-service.", "Microservice destination discrepancy"),
        ("Fetch payment history for customer_id=cust_AAA", "Fetch payment history for customer_id=cust_BBB", "Customer ID entity mismatch"),
        ("Update DNS A record for api.domain.com", "Update DNS A record for admin.domain.com", "Subdomain entity substitution"),
        ("Query database postgres_inventory", "Query database postgres_accounting", "Database schema entity substitution"),
        ("Delete user avatar for profile_id=5501", "Delete user avatar for profile_id=9902", "Profile ID substitution"),
        ("Provision VPC in AWS account 111122223333", "Provision VPC in AWS account 444455556666", "Cloud account ID mismatch"),
        ("Rotate secret token for service_account_dev", "Rotate secret token for service_account_prod", "Environment service account substitution"),
        ("Transfer domain ownership to Registrar Corp", "Transfer domain ownership to Host Global", "Registrar entity substitution"),
        ("Assign issue PROJ-101 to Developer Dan", "Assign issue PROJ-101 to Developer Sara", "Assignee entity substitution"),
        ("Execute benchmark on instance type c6g.xlarge", "Execute benchmark on instance type r6g.8xlarge", "Instance class entity mismatch"),
        ("Download audit log from bucket s3://prod-logs", "Download audit log from bucket s3://test-logs", "S3 bucket entity mismatch"),
        ("Bind SSL certificate cert_2024_wildcard", "Bind SSL certificate cert_2023_legacy", "Certificate entity substitution"),
        ("Post message to Slack channel #announcements", "Post message to Slack channel #engineering-alerts", "Slack channel destination mismatch"),
        ("Revoke OAuth token client_id=mobile_ios", "Revoke OAuth token client_id=web_spa", "Client ID entity substitution"),
        ("Publish artifact to repository maven-releases", "Publish artifact to repository maven-snapshots", "Repository entity substitution"),
        ("Set primary gateway IP to 192.168.1.1", "Set primary gateway IP to 10.0.0.1", "Network IP entity mismatch"),
    ]

    for a, b, reason in entity_templates:
        for variation in range(5):
            dataset.append({
                "id": f"ent_{idx:04d}",
                "category": "entity_substitution",
                "prompt_a": a if variation % 2 == 0 else f"Execute: {a}",
                "prompt_b": b if variation % 2 == 0 else f"Execute: {b}",
                "expected_match": False,
                "reason": reason,
            })
            idx += 1

    # 6. VALID SEMANTIC PARAPHRASES (Expected match: TRUE - Legitimate cache hits)
    valid_paraphrase_templates = [
        ("What is the capital of France?", "Tell me what city serves as the French capital.", "Capital city synonymy"),
        ("How do I reset my account password?", "What are the steps to change my login password?", "Password reset rephrasing"),
        ("Explain how RSA public key encryption works.", "Can you explain how RSA public key cryptography operates?", "RSA encryption explanation paraphrase"),
        ("Write a Python function to compute the Fibonacci sequence.", "Provide a Python script for calculating the Fibonacci sequence.", "Fibonacci Python code request"),
        ("What is the difference between synchronous and asynchronous programming?", "What distinguishes asynchronous code execution from synchronous programming?", "Sync vs async explanation"),
        ("How does TLS 1.3 zero round trip time handshake work?", "Describe how zero round trip time resumption works in TLS 1.3 protocol.", "TLS 0-RTT explanation paraphrase"),
        ("Explain the CAP theorem with distributed database examples.", "Describe the CAP theorem trade-offs in distributed data stores.", "CAP theorem distributed systems paraphrase"),
        ("What are the ACID guarantees in relational databases?", "Explain atomicity, consistency, isolation, and durability in DBMS.", "ACID database explanation"),
        ("How do B-trees differ from LSM trees in database storage engines?", "Compare B-tree indexes against log structured merge trees for databases.", "B-tree vs LSM tree comparison"),
        ("What is the purpose of Docker multi-stage builds?", "Why should developers use multi-stage Docker builds?", "Docker multi-stage explanation"),
        ("Explain Kubernetes pod lifecycle and restart policies.", "How do pod lifecycles and restart policies function in K8s?", "Kubernetes pod lifecycle explanation"),
        ("How do quantum computers factor large composite integers?", "Explain integer factorization algorithms on quantum computing hardware.", "Quantum factorization explanation"),
        ("What is eBPF and how does it enable Linux kernel observability?", "Explain how eBPF programs monitor Linux kernel subsystem events.", "eBPF Linux observability explanation"),
        ("What are zero knowledge proofs and zk-SNARKs?", "Explain the mathematics and concepts behind zk-SNARK zero knowledge proofs.", "Zero knowledge proofs explanation"),
        ("How does vector quantization work in Annoy and HNSW vector databases?", "Describe vector quantization indexing in similarity search engines.", "Vector quantization similarity search"),
        ("How does the Raft consensus algorithm perform leader election?", "Explain leader election mechanisms in Raft distributed consensus.", "Raft consensus leader election"),
        ("What is the difference between TCP and UDP networking protocols?", "Compare transmission control protocol against user datagram protocol.", "TCP vs UDP networking comparison"),
        ("How does garbage collection work in the Go runtime?", "Explain memory allocation and garbage collection in Golang.", "Go runtime garbage collection explanation"),
        ("What is an idempotent API endpoint in REST design?", "Explain idempotency principles in HTTP RESTful web services.", "REST idempotency explanation"),
        ("How does OAuth 2.0 authorization code grant flow work?", "Describe the step by step process of OAuth2 authorization code exchange.", "OAuth 2.0 auth flow explanation"),
        ("What is the difference between process and thread in operating systems?", "Contrast operating system processes with execution threads.", "Process vs thread OS concept"),
        ("How does consistent hashing work in distributed caching?", "Explain consistent hashing rings for distributed cache partitioning.", "Consistent hashing distributed caching"),
    ]

    for a, b, reason in valid_paraphrase_templates:
        for variation in range(5):
            dataset.append({
                "id": f"para_{idx:04d}",
                "category": "valid_paraphrase",
                "prompt_a": a if variation % 2 == 0 else f"Hello, {a}",
                "prompt_b": b if variation % 2 == 0 else f"Hello, {b}",
                "expected_match": True,
                "reason": reason,
            })
            idx += 1

    return dataset


def main() -> None:
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset = build_dataset()
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        for item in dataset:
            f.write(json.dumps(item) + "\n")

    print(f"[+] Generated {len(dataset)} semantic safety evaluation prompt pairs at: {DATASET_PATH}")
    categories = {}
    for item in dataset:
        categories[item["category"]] = categories.get(item["category"], 0) + 1
    for cat, count in categories.items():
        print(f"    • {cat}: {count} pairs")


if __name__ == "__main__":
    main()
