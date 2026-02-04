FROM kalilinux/kali-rolling

RUN apt-get update
RUN apt -y upgrade
RUN apt -y install kali-linux-arm

RUN apt -y install tightvncserver dbus dbus-x11 novnc net-tools

COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]