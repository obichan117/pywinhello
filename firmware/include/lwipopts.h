/*
 * lwipopts.h — lwIP options for pywinhello (Pico W only)
 *
 * Minimal configuration: DHCP + DNS + UDP (for NTP).
 * No TCP server, no HTTP, no MQTT — just time sync.
 */

#ifndef LWIPOPTS_H
#define LWIPOPTS_H

/* Use Pico W defaults as base, then customize */
#define NO_SYS                      1
#define LWIP_SOCKET                 0
#define LWIP_NETCONN                0

/* Memory */
#define MEM_LIBC_MALLOC             0
#define MEM_SIZE                    4096
#define MEMP_NUM_PBUF               16
#define PBUF_POOL_SIZE              16

/* Core protocols */
#define LWIP_ARP                    1
#define LWIP_ICMP                   1
#define LWIP_RAW                    0
#define LWIP_UDP                    1
#define LWIP_TCP                    1

/* DHCP (get IP address from router) */
#define LWIP_DHCP                   1
#define LWIP_DHCP_CHECK_LINK_UP     1

/* DNS (resolve NTP server hostname) */
#define LWIP_DNS                    1
#define DNS_MAX_SERVERS             2

/* Timeouts */
#define DHCP_DOES_ARP_CHECK         0

/* Debugging - disabled for release */
#define LWIP_DEBUG                  0

#endif /* LWIPOPTS_H */
