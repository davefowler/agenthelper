i want to make here a very simple python tool that uses the gh cli tool (and or api) to periodically check github for updates to pr's or issues that an agent has made or an action has completed.

i am frequently checkin in on pr's and having to say "@cursor there are test/linting/other issues - fix these." to kick off the cursor agents working again.

similarly i now have claude giving code reviews and if there is legit stuff there i just say "@cursor review and fix the issues claude brought up"

i tried to automate this with github actions but tagging "@cursor" with github actions does not work.  it has to be from me (or my gh cli).

i'd like to have an LLM do these simple check-in/nudges to continue work for me.  how should we do this?  make a plan.
