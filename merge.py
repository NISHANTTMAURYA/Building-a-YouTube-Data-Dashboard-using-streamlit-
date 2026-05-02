with open("app.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "final_channel_id = st.session_state.selected_channel_id" in line:
        break

with open("app.py", "w") as f:
    for line in new_lines:
        f.write(line)
    with open("new_logic.py", "r") as fl:
        f.write("\n")
        f.write(fl.read())
