#/bin/bash

# check if there is user em340, if not, create user and group
if ! id -u em340 >/dev/null 2>&1; then
    echo "user em340 not found, creating user and group"
    groupadd em340
    useradd -g em340 em340
else
    echo "user em340 found"
fi

# check if python package venv is installed
if ! python3 -c "import venv" >/dev/null 2>&1; then
    echo "python package venv not found, installing package"
    python3 -m pip install venv
else
    echo "python package venv found"
fi

# check if venv is created
if [ ! -d "venv" ]; then
    echo "venv not found, creating venv"
    python3 -m venv venv

    chown -R em340:em340 venv

    # activate venv
    source venv/bin/activate

    # upgrade pip
    pip install --upgrade pip

    # install requirements
    pip install -r requirements.txt

    # deactivate venv
    deactivate

    # find line in venv/bin/activate with string VIRTUAL_ENV and replace it with VIRTUAL_ENV=/opt/em340d/venv
    sed -i 's/VIRTUAL_ENV=\".*\"/VIRTUAL_ENV=\"\/opt\/em340d\/venv\"/g' venv/bin/activate

    echo "venv created"
else
    echo "venv found"
fi

# check if user em340 is in group dialout
if ! id -nG em340 | grep -qw dialout; then
    echo "user em340 not in group dialout, adding user to group"
    usermod -a -G dialout em340
else
    echo "user em340 found in group dialout"
fi

# check if there is a directory for logging /var/log/em340d and owned by em340
if [ ! -d "/var/log/em340d" ]; then
    echo "directory /var/log/em340d not found, creating directory"
    mkdir /var/log/em340d
    chown em340:em340 /var/log/em340d
else
    echo "directory /var/log/em340d found"
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
