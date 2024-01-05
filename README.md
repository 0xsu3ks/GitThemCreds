# GitThemCreds v2.0

Any questions or feedback please reach out to me in Mattermost or Teams.

To use this script you will need a GitHub Fine Grained Access Token.

https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token

Steps:
1. Login to GitHub
2. Go to Settings
3. Scroll to bottom and on left hand side click Developer
4. Generate a Fine Grained Access Token, it begins with "github_pat_XXXXX"
5. Paste into config file

## Version 2.0 Changes
+ Script is now broken up into modules {enum, git, aws, bitbucket} with each module having its own flags

#### Enum Module
+ Commands here are:
	- config
	- domain
	- truffles
	- pages
	- table
	- check-token

The help menu describes the purpose of each but the main change in v2 is that the `--check-token` flag will check the validity of a token. 

**No OPSEC concerns here from a red team perspective.**

#### Git Module
+ Commands here are:
	- token
	- repos
	- clone

This new module automates the entire process of listing and cloning the repos of the authenticated user. Depending on token permissions it can list private repos and clone those as well. 

**No OPSEC concerns here from a red team perspective.**

#### AWS Module
When using the AWS CLI from a kali machine, the user agent string is set to `User-Agent: Boto3/1.7.29 Python/2.7.6 Linux/4.14.0-kali3-amd64 Botocore/1.10.29`

This should trigger the CloudWatch `PenTest:IAMUser/KaliLinux` alert.

To avoid this detection I simply set the useragent string in the python script to override what Boto3 supplies, the new useragent string is:
`Boto3/1.9.89 Python/2.7.12 Linux/4.2.0-42-generic` which make it seem like it's coming from a regular Linux distro like Arch or Ubunutu. 

Some research on this topic can be found here:
https://www.thesubtlety.com/post/patching-boto3-useragent/

(I go with a simpler method than the monkeypatching used here but still the same result. You can uncomment line 408 and double check for yourself.)

+ Commands here are:
	- access-key
	- secret-key
	- session
	- session-url

This supports temporary AWS credentials and can even generate a console login link for temporary credentials with the `--session-url` parameter.

**Because of these changes I do believe there are any OPSEC concerns from a red team perspective**

#### Bitbucket Module
This one is hard to implement without knowing the Bitbucket URL, but you can pass the `bitbucket` module to the script and recieve a curl command that you can use as a skeleton.

## Screenshots (commands have changed)

![Searching GitHub API](./images/GitThemCreds-APISearch.png)


![Table for Screenshots](./images/GitThemCreds-Table.png)


![Hunting for Secrets](./images/GitThemCreds-Truffle.png)



## Install
`./setup.sh`

## How It Works
GitThemCreds.py is a python that script that will  search the GitHub API code base searching for a domain you supply like `example.com` + queries loaded from a configuration file.

For example 
`GitThemCreds.py enum example.com `


It also allows to use a GitHub API token to clone and repos associated with the token.

For example
`GitThemCreds.py git --token XXXXXXXXX --repos --clone`

You can also check the validity of an AWS token without worry

For example
`GitThemCreds.py aws --access-key AKIAABCD1234 --secret-key +dsdjidjI(RJfmso)`

![Verify Keys](./images/GitThemCreds-VerifyKeys.png)

GitHub is super sensitive to this type of "scraping" or "searching" and has various mechanisms to rate limit the request. To avoid this limitation, there is a hefty pause between queries, around one minute each iteration. You can change this in the script but be aware you'll run into rate limiting fairly quickly.

Some more information here about GitHub's rate limiting nonsense:

https://docs.github.com/en/rest/overview/resources-in-the-rest-api?apiVersion=2022-11-28

If the script runs into rate limiting issues it will slowly begin to add time inbetween reqeusts.

The script will also stream the urls/responses in real time to a text file and also dump the raw JSON for querying with `jq`

Once URLs are collected it runs them through `trufflehog` searching for secrets.

The objective here is to support Red Team Ops by automating the GitHub recon aspect. Everything here is **passive** enumeration so at the beginning of an engagment, start this script in a screen session and let it work, while you continue to focus on other things. Come back later and review the trufflehog report.

## Usage
`python3 GitThemCreds.py --help`

![GitThemCreds Help Menu](./images/GitThemCreds-help.png]]

Currently there are 4 modules, each one with it's own set of commands


## FAQ
+ Can I change the trufflehog command?
	+ Currently you need to edit the python script 
		```            
		    command = f'./trufflehog git {url} | tee -a truffle-report.txt'
            #Need this subprocess to do this
            subprocess.run(command, shell=True, check=True)
     This is found in line 288 in the python script.

+ Why does this take so long?
	+ The GitHub API is super restrictive of it's Code Search API. This script is meant to support Read Team Ops during an engagment and can take a few minutes to hours to complete depending on the organization's exposure on GitHub.
