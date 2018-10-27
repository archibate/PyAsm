!def _text
	mov %edx, #1
	mov %edx, $_start
	mov %edx, $boxa+23
!def boxc
	mov %edx, $_start+4
	mov %edx, $box-1
	mov %edx, $boxc+3
!def boxd
	mov %edx, $boxa+12
	nop
!def _start
	cli
	hlt
