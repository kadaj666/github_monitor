Github Monitor 
======
Scaning github repos and sent a webhook if new release or tag appears

### Prepare it

1. Edit **config.json** and add your required repositories or tags
2. In **github_monitoring.py** add your [Github Bearer Token](https://docs.github.com/en/rest/overview/authenticating-to-the-rest-api?apiVersion=2022-11-28)  to var **github_auth**
3. Change webhook url for alerting in **webhook_url** (you can set a telegram webhook instead of oncall)


### Install or build options

option 1: Just build container using dockerfile

option 2: 
```bash
pip3 install -r requirements.txt
python github_monitoring.py --config config.json
```
option 3: Build container using gitlab ci file

### Additional info

You can change check interval in file **github_monitoring.py** at line 
```python
scheduler.add_job(job_for_scheduler, "interval", hours=1, args=[config]) # change the interval hours=1 as you like
```
**Script using a sqlite db to keep releases and tags and compare if new apear, make sure what path exist and make it persistent if you using docker**
```python
bd_path = "/opt/monitoring/db/github_monitoring.db"  #path to database (make persistent if in docker)
```
