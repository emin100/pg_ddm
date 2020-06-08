FROM ubuntu:20.04
LABEL maintainer="emin100@gmail.com"

RUN apt-get update && apt-get install -y tzdata


RUN apt-get update && apt-get install -y gnupg
# Add the PostgreSQL PGP key to verify their Debian packages.
# It should be the same key as https://www.postgresql.org/media/keys/ACCC4CF8.asc
RUN apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8

# Add PostgreSQL's repository. It contains the most recent stable release
#     of PostgreSQL, ``11``.
RUN echo "deb http://apt.postgresql.org/pub/repos/apt/ focal-pgdg main" > /etc/apt/sources.list.d/pgdg.list

# Install ``python-software-properties``, ``software-properties-common`` and PostgreSQL 11
#  There are some warnings (in red) that show up during the build. You can hide
#  them by prefixing each apt-get statement with DEBIAN_FRONTEND=noninteractive
RUN apt-get install -y  postgresql postgresql-client postgresql-contrib \
make etcd virtualenv libevent-dev pkg-config openssl libtool m4 autotools-dev automake libssl-dev ruby ruby-dev vim git

RUN apt-get install -y wget

#Install pandoc 2.7
RUN wget https://github.com/jgm/pandoc/releases/download/2.7.2/pandoc-2.7.2-1-amd64.deb
RUN dpkg -i  pandoc-2.7.2-1-amd64.deb
RUN rm -rf pandoc-2.7.2-1-amd64.deb

RUN ln -s `which python3` /usr/bin/python

# Note: The official Debian and Ubuntu images automatically ``apt-get clean``
# after each ``apt-get``

# Run the rest of the commands as the ``postgres`` user created by the ``postgres-11`` package when it was ``apt-get installed``
USER postgres

# Create a PostgreSQL role named ``docker`` with ``docker`` as the password and
# then create a database `docker` owned by the ``docker`` role.
# Note: here we use ``&&\`` to run commands one after the other - the ``\``
#       allows the RUN command to span multiple lines.
RUN    /etc/init.d/postgresql start &&\
    psql --command "CREATE USER docker WITH SUPERUSER PASSWORD 'docker';" &&\
    createdb -O docker docker



# Adjust PostgreSQL configuration so that remote connections to the
# database are possible.
RUN echo "host all  all    0.0.0.0/0  md5" >> /etc/postgresql/12/main/pg_hba.conf

# And add ``listen_addresses`` to ``/etc/postgresql/11/main/postgresql.conf``
RUN echo "listen_addresses='*'" >> /etc/postgresql/12/main/postgresql.conf

USER root
RUN useradd -ms /bin/bash pg_ddm



#RUN mkdir /etc/pgbouncer


ADD tools/install.sh /usr/bin/
RUN /usr/bin/install.sh /home/pg_ddm 1 pg_ddm 1
#
ADD tools/control-change.sh /usr/bin/
#
#RUN chown -R postgres:postgres /etc/pgbouncer
#RUN mkdir /var/run/pgbouncer && chown postgres:postgres /var/run/pgbouncer
#RUN mkdir /var/log/pgbouncer && chown postgres:postgres /var/log/pgbouncer




#WORKDIR /etc/pgbouncer


# Expose the PostgreSQL port
EXPOSE 5432
EXPOSE 2379
EXPOSE 15432
EXPOSE 25432

# Add VOLUMEs to allow backup of config, logs and databases
VOLUME  ["/etc/postgresql", "/var/log/postgresql", "/var/lib/postgresql"]

ENTRYPOINT /usr/bin/control-change.sh
