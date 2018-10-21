!orgv 0x7c00
	mov %edx, #1
	mov %edx, $_start
	mov %edx, $boxa
!def boxa
	mov %edx, $_start+4
	mov %edx, $box
	mov %edx, $boxa
	nop
!def _start
	cli
	hlt
