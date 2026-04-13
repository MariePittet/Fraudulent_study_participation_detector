# Fraudulent study participation detector

This Streamlit app detects fraudulent participation to an online study with 3 cognitive tasks (Go-NoGo, Approach-Avoidance Task, 2-Alternatives Forced-Choice). It flags speed-running, excessive inattention, bot completion.
Caution: in our case, study participants are informed prior to participation and prior to starting the tasks that such algorithm will be applied and that compensation will be denied for fraudulent behavior.

### How to use
- Open the [Streamlit app](https://fraudulentstudyparticipationdetector.streamlit.app/) in your browser
- Drop participants' csv files: you can drop multiple files per participant, and multiple participants (they will be grouped by ID)
- Read the fraud report: see if some participants' files are flagged as suspicious and why exactly, inspect trial distributions
- Chase fraudsters and deny study compensation money

### Fraud flagging rules

| Rule | Threshold | Behavior flagged |
| :--- | :--- | :--- |
| All tasks low RT variability | IQR <75ms | Button mashing or bot completion |
| All tasks speed-running | > 15% trials below mininmal RTs* | Speed-running |
| GNG high false alarm rate | > 45% on NoGo trials | Always pressing to rush regardless of stimulus type |
| GNG high miss rate | > 35 % on Go trials | Letting the task run while doing something else |
| 2AFC same-side streak | > 12 consecutive trials | Always chosing the same side to rush |
| AAT high error rate | > 35% incorrect trials | Ignoring rules to rush or responding randomly without focusing |
| AAT same-response streak | > 12 consecutive trials |  Always avoiding or approaching to rush |

_* Minimal RTs are 250ms for GNG and AAT, and 200ms for 2AFC since preference may induce quicker RTs for highly recognized and liked items than external rules_

### No data but wanna feel the thrill of catching villains ?
Use the data in fraudulent_data_examples to drop in the app. 

