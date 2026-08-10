# Oracle Cloud Cost Estimates & Tracking

This document records the estimated costs of the servers provisioned on the Oracle Cloud account to help track the burn rate of the $300 USD ($400 SGD) 30-Day Trial Credits.

> [!NOTE]
> **Important Rule about Oracle Pricing Estimates:** 
> The Oracle Cloud creation screen shows the *gross* estimated cost. It does **not** reflect the "Always Free" tier discounts. For example, Oracle shows the Boot Volume as costing ~$5.87/month, but because you get 200 GB for free, the *actual* amount billed to your credits for the Boot Volume will be $0.00.

---

---

## The Trial Server (Intel x86 Fallback)
**Date Recorded:** June 2026
**Configuration:** 
- **Shape:** `VM.Standard3.Flex` (Intel)
- **CPUs:** 2 OCPUs
- **RAM:** 12 GB
- **Boot Volume:** 100 GB (10 VPU Balanced)

### Oracle's Estimated Cost:
- **Compute instance:** $100.76 / month
- **Boot volume:** $5.87 / month
- **Estimated total:** $106.63 / month

### Burn Rate Analysis:
If the AMD shape is "Out of capacity", the Intel shape is slightly more expensive per OCPU. 
Since this configuration costs roughly $106.63 for a full 30-day month, you are burning about **$3.55 per day**. 

By the end of your 30-day trial, this server will consume ~$106 of your credits. You still have nearly $200 of your free credits remaining, which means this Intel fallback is still completely safe for the duration of the trial!
