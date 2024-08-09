
# Issue: Invalid JWT Token in Google Cloud Authentication

## Summary

This document details the issue encountered with an invalid JWT token during Google Cloud API authentication, along with the steps taken to diagnose and resolve the problem.

## Issue Description

**Error Message:**

When running the Flask application, the following error was encountered:

```
ERROR:root:Token refresh error: ('invalid_grant: Invalid JWT: Token must be a short-lived token (60 minutes) and in a reasonable timeframe. Check your iat and exp values in the JWT claim.', {'error': 'invalid_grant', 'error_description': 'Invalid JWT: Token must be a short-lived token (60 minutes) and in a reasonable timeframe. Check your iat and exp values in the JWT claim.'})
```

**Symptoms:**
- The list of supported languages was not populating in the frontend.
- The error logs indicated issues with the JWT token's "issued at" (`iat`) and "expiration" (`exp`) values.

## Diagnosis

The issue was related to the system time being out of sync, which caused the JWT tokens to be considered invalid. The following steps were taken to diagnose the problem:

1. **Checked System Time:**
   - The system time was found to be slightly off, leading to the invalidation of JWT tokens.

2. **Attempted Time Synchronization:**
   - Tried to sync the system time using `ntpdate`, `timedatectl`, and `systemsetup`, but encountered errors.

3. **Successfully Synchronized Time:**
   - Finally, used `sntp` to synchronize the system time with Google's NTP server (`time.google.com`).

## Resolution

### Steps Taken

1. **Synchronized System Time Using SNTP:**
   - Ran the following command to synchronize the system time:
     ```bash
     sudo sntp -sS time.google.com
     ```
   - The output indicated a successful time synchronization:
     ```
     -0.002140 +/- 0.037003 time.google.com 216.239.35.4
     ```

2. **Restarted the Flask Application:**
   - After synchronizing the time, restarted the application to check if the issue was resolved.

3. **Verified the Solution:**
   - The supported languages were successfully populated, and no further JWT token errors were encountered.

## Future Prevention

To prevent this issue from recurring:

1. **Monitor System Time:**
   - Ensure that the system time remains synchronized, especially on servers that run continuously.

2. **Document the Time Sync Process:**
   - Keep this document handy to quickly resolve the issue by re-syncing the system time.

3. **Consider Automated Time Sync:**
   - Implement automated time synchronization using `ntpd`, `chrony`, or `timedatectl` to avoid manual intervention.

## References

- [Google Cloud Authentication Error Documentation](https://cloud.google.com/docs/authentication)
- [NTP Server Documentation](https://www.ntp.org/documentation.html)
- [Google Client Invalid JWT: Token must be a short-lived token](https://stackoverflow.com/questions/48056381/google-client-invalid-jwt-token-must-be-a-short-lived-token)
