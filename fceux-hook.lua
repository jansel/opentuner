player_state_addr = 0x000E;
player_state_dying = 6;
player_float_addr = 0x001D;
player_float_flagpole = 3;
player_horizpos_addr = 0x006D;
minimum_frames = 197;

function maybe_died()
	--if (emu.framecount() < minimum_frames) then
	--	return;
	--end;
	local x = memory.readbyte(player_state_addr);
	if (x == player_state_dying) then
		io.write("died ", math.floor(memory.readbyte(player_horizpos_addr)), "\n");
		os.exit();
	end;
end

function maybe_won()
	--if (emu.framecount() < minimum_frames) then
	--	return;
	--end;
	local x = memory.readbyte(player_float_addr);
	if (x == player_float_flagpole) then
		io.write("won ", math.floor(emu.framecount()), "\n");
		os.exit(0);
	end;
end	

emu.speedmode("maximum");
while true do
	if (emu.framecount() > minimum_frames) then
		maybe_died();
		maybe_won();
	end;
	emu.frameadvance();
end
--memory.register(player_state_addr, maybe_died);
--memory.register(player_float_addr, maybe_won);
