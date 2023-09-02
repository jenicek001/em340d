#/bin/bash

# check if there is user em340, if not, create user and group
if ! id -u em340 >/dev/null 2>&1; then
    echo "user em340 not found, creating user and group"
    groupadd em340
    useradd -g em340 em340
else
    echo "user em340 found"
fi

# check if venv is created
if [ ! -d "venv" ]; then
    echo "venv not found, creating venv"
    python3 -m venv venv

    # activate venv
    source venv/bin/activate

    # upgrade pip
    pip install --upgrade pip

    # install requirements
    pip install -r requirements.txt

    # deactivate venv
    deactivate

    echo "venv created"
else
    echo "venv found"
fi

# check if service is installed
if [ ! -f "/etc/systemd/system/em340d.service" ]; then
    echo "service not found, installing service"

    # copy service file to systemd
    cp em340d.service /etc/systemd/system/

    # reload systemd
    systemctl daemon-reload

    # enable service
    systemctl enable em340d.service
else
    echo "service found - stopping service"
    systemctl stop em340d.service
fi

# copy whole directory to /opt
cp -r . /opt/em340d

# change owner of /opt/em340d to em340
chown -R em340:em340 /opt/em340d

# make em340.sh executable
chmod +x /opt/em340d/em340.sh

systemctl start em340d.service
sleep 5
systemctl status em340d.service

# check return code
if [ $? -eq 0 ]; then
    echo "Installation successful"
else
    echo "Installation failed"
fi
