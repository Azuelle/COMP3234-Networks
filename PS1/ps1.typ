

#align(center)[
#text(18pt)[
*COMP3234 / Written Assignment 1*
]

#smallcaps("Tang") Jiakai · UID 3035974119
]

#show heading: it => block({it})
#set enum(numbering: "a.")

= Question 1

+ When circuit switing is used, 50 users can be supported.
+ The probability of a given user transmitting is 10%.
+ The probability of $n$ users transmitting simulatenously is $binom(120, n) 0.1^n 0.9^(120 - n)$.
+ The probability of 51 or more users transmitting simulatenously is $sum_(i = 51)^(120) [binom(120, i) 0.1^i 0.9^(120 - i)]$.

= Question 2

+ The bandwith-delay product is $R dot d_"prop" = 5 "Mbps" dot (20000 "km")/(2.5 dot 10^8 "m/s") = 0.4 "Mb"$.
+ The maximum number of bits in the link at any given time is $0.4 "Mb" = 400000 "bits"$.
+ The bandwith-delay product can be interpreted as the maximum number of bits in the link at any given time.
+ The width of a bit in the link is $(20000 "km") / (400000 "bits") = 50 "m "$.
+ The general expression for the width of a bit is $R dot d_"prop" = (R m)/s$.

= Question 3

The most popular servers can be determined by checking the number of records in the DNS cache for each server. The ones with the most records are the most popular servers.

= Question 4

+ A distribution scheme where the server sends data to every client at rate $u_"s " slash N$ can achieve a distribution time of $F slash (u_"s " slash N) = N F slash u_"s "$.

+ A distribution scheme where the server sends data to every client $i$ at rate $min{d_i, u_"s " slash N}$ can achieve a distribution time of $F slash d_"min"$ because the slowest determines the distribution time.

+
  - For $u_"s " slash N <= d_"min"$, $1 slash d_"min" <= N slash u_"s "$, $max{N F slash u_"s ", F slash d_"min"} = N F slash u_"s "$.

  - For $d_"min" <= u_"s " slash N$, $1 slash d_"min" >= N slash u_"s "$, $max{N F slash u_"s ", F slash d_"min"} = F slash d_"min"$.

  Therefore, the minimum distribution time is given by $max{N F slash u_"s ", F slash d_"min"}$.

= Question 5

- The sum of these 8-bit bytes is `1` `0010` `1101`. With wraparound, it becomes `0010` `1110`. Its 1's complement is `1101` `0001`.

- The reason 1's complement is used is that it makes error-checking easier. The checksum can be simply added to the sum, and if the data has no errors, the result would have `1` on every bit. If there is `0` in the result, the receiver would know that there is an error.

- A 1-bit error would flip at least one bit in the sum, and hence the same for the checksum. Therefore, it is impossible for a 1-bit error to go undetected.

- A 2-bit error could go undetected by "swapping" two bits in the bytes. For example, changing `1111` `1101`, `0000` `0010` to `1111` `1111`, `0000` `0000` would result in the same sum and checksum. Thus, despite 2 bits had been flipped, the receiver would not be able to detect the error.

= Question 6

+
  / GBN: Host A sends 9 segments in total: 1, 2, 3, 4, 5, 2, 3, 4, 5; host B sends 8 ACKs in total: 1, 1, 1, 1, 2, 3, 4, 5.

  / SR: Host A sends 6 segments in total: 1, 2, 3, 4, 5, 2; host B sends 5 ACKs in total: 1, 3, 4, 5, 2.

  / TCP: Host A sends 6 segments in total: 1, 2, 3, 4, 5, 2; host B sends 5 ACKs in total: 2, 2, 2, 2, 6.

+ If the timeout values for all three protocols are much longer than 5 RTT, TCP would deliver all five data segments in the shortest time interval.

  The reason is that the receiver would send a duplicate ACK for segment \#2 immediately after receiving segments with higher-than-expected sequence numbers (\#3, \#4, \#5). This allows the sender to start retransmitting lost segment \#2 after just 1 RTT, completing the transmission in just 2 RTT.

  In contrast, GBN and SR would have to wait for a timeout (much longer than 5 RTT) to begin retransmission.