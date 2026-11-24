# #Questions
# 1 How many requests are in the log? (Should malformed lines count?)
# 2 What are the top 5 IPs by number of requests?
# 3 How many requests got each status code?
# 4 How many requests were server errors (5xx)?
# 5 Which 5 endpoints (paths) were requested most?
# 6 How many requests were there per hour?
# 7 What are the 5 slowest requests? (Show the path and the time.)
# 8 Which IPs tried to access /admin or /wp-login.php?
# 9 How many distinct IPs visited?
# 10 How many lines are malformed, and what are they?
set -euo pipefail

#Question 1:
grep -nc "HTTP/1.1" access.log

#Question 2:
awk '{print$1}' access.log | sort -n | uniq -c | sort -rn | head -n 5

#Question 3:
grep "HTTP/1.1" access.log | awk '{print $9}'| sort -n | uniq -c | sort -rn 

#Question 4:
awk '($9 >= 500) && ($9 <=600){print$9}' access.log | wc -l
#or
awk '$9 >= 500 && $9 < 600 {n++} END {print n}' access.log

#Question 5:
grep "HTTP/1.1" access.log | awk '{print $7}'| sort | uniq -c | sort -rn

#Question 6:
grep "HTTP/1.1" access.log | awk -F ':' '{print $2}'| sort | uniq -c | sort 

#Question 7:
grep "HTTP/1.1" access.log | awk '{print $NF, $7`}'| sort -rn | head -n 5

#Question 9:
grep "HTTP/1.1" access.log | awk '{print $1}' | sort | uniq -c | grep -nc .
#or
grep "HTTP/1.1" access.log | awk '{print $1}' | sort -u | wc -l

#Question 10:
grep -vnc "HTTP/1.1" access.log 

grep -vn` "HTTP/1.1" access.log 