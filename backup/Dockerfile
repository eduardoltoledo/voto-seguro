FROM postgres:16
COPY --chmod=755 backup/backup.sh /backup.sh
COPY --chmod=755 backup/restaurar.sh /restaurar.sh
RUN sed -i 's/\r$//' /backup.sh /restaurar.sh
ENTRYPOINT ["/backup.sh"]
