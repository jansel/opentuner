player_state_addr = 0x000E;
player_state_dying = 6;
player_float_addr = 0x001D;
player_float_flagpole = 3;
player_page_addr = 0x006D;
player_horizpos_addr = 0x0086;
minimum_frames = 197;

emu.speedmode("maximum");
while true do
	if (emu.framecount() > minimum_frames) then
		--dead?
		local dead = memory.readbyte(player_state_addr) == player_state_dying;
		--flagpole?
		local won = memory.readbyte(player_float_addr) == player_float_flagpole;
		if (dead or won) then
			local str = (dead and "died" or "won");
			local x_pos = math.floor(memory.readbyteunsigned(player_page_addr)*256 + memory.readbyteunsigned(player_horizpos_addr));
			local framecount = emu.framecount();
			io.write(str, " ", x_pos, " ", framecount, "\n");
			os.exit(0);
		end;
	end;
	emu.frameadvance();
end
