"""
pth_binary_patcher.py — Parse Java serialized .pth file, track byte offsets,
identify EgressAgent behavior references, and patch them to new Behavior handles.

Does NOT rely on javaobj for re-serialization. Instead:
  1. Custom byte-level parser tracks offset of every object and reference
  2. Uses javaobj (read-only) to navigate the object graph and determine
     which agents need behavior changes
  3. Binary patches the TC_REFERENCE handles in-place

Java Serialization Protocol (brief):
  TC_OBJECT     = 0x73  — new object
  TC_CLASSDESC  = 0x72  — class descriptor
  TC_REFERENCE  = 0x71  — reference to previous object (4-byte handle follows)
  TC_STRING     = 0x74  — string (2-byte UTF length + data)
  TC_BLOCKDATA  = 0x77  — block of primitive data (1-byte length + data)
  TC_ENDBLOCK   = 0x78  — end of optional data block
  TC_NULL       = 0x70  — null reference
  TC_ARRAY      = 0x75  — array
  TC_CLASS      = 0x76  — class
  TC_LONGSTRING = 0x7A  — long string
  Base wire handle = 0x7E0000
"""

import io
import struct
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── Protocol constants ──────────────────────────────────────

TC_NULL        = 0x70
TC_REFERENCE   = 0x71
TC_CLASSDESC   = 0x72
TC_OBJECT      = 0x73
TC_STRING      = 0x74
TC_ARRAY       = 0x75
TC_CLASS       = 0x76
TC_BLOCKDATA   = 0x77
TC_ENDBLOCKDATA = 0x78
TC_LONGSTRING  = 0x7A
BASE_HANDLE    = 0x7E0000

SC_SERIALIZABLE   = 0x02
SC_WRITE_METHOD   = 0x01
SC_EXTERNALIZABLE = 0x04
SC_BLOCK_DATA     = 0x08


class JavaSerialStream:
    """Byte-level Java serialization stream parser with offset tracking."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.handles: list[dict] = []  # handle_index → {offset, class_name, type}
        # For each handle, store the offset where the object STARTS in the stream

    def read_byte(self) -> int:
        b = self.data[self.pos]
        self.pos += 1
        return b

    def read_ushort(self) -> int:
        v = struct.unpack_from(">H", self.data, self.pos)[0]
        self.pos += 2
        return v

    def read_int(self) -> int:
        v = struct.unpack_from(">i", self.data, self.pos)[0]
        self.pos += 4
        return v

    def read_long(self) -> int:
        v = struct.unpack_from(">q", self.data, self.pos)[0]
        self.pos += 8
        return v

    def read_float(self) -> float:
        v = struct.unpack_from(">f", self.data, self.pos)[0]
        self.pos += 4
        return v

    def read_double(self) -> float:
        v = struct.unpack_from(">d", self.data, self.pos)[0]
        self.pos += 8
        return v

    def read_utf(self, length: int) -> str:
        s = self.data[self.pos:self.pos + length].decode("utf-8")
        self.pos += length
        return s

    def handle_for_index(self, idx: int) -> int:
        return BASE_HANDLE + idx

    def parse(self) -> list[dict]:
        """Parse the entire stream, returning list of handle records.
        Each record: {handle, offset, class_name, fields: {name: {type, offset, ref_handle}}}
        """
        self.pos = 0
        self.handles = []

        # Read stream header
        magic = self.read_ushort()
        version = self.read_ushort()
        if magic != 0xACED:
            raise ValueError(f"Bad stream magic: 0x{magic:04X}")
        if version != 5:
            raise ValueError(f"Unsupported stream version: {version}")

        # Parse contents
        self._parse_content()

        return self.handles

    def _parse_content(self):
        """Parse content elements until stream exhausted."""
        while self.pos < len(self.data):
            tc = self.read_byte()
            if tc == TC_OBJECT:
                self._parse_new_object()
            elif tc == TC_STRING:
                self._parse_new_string()
            elif tc == TC_REFERENCE:
                self._parse_reference()
            elif tc == TC_NULL:
                self._parse_null()
            elif tc == TC_ARRAY:
                self._parse_new_array()
            elif tc == TC_CLASS:
                self._parse_class()
            elif tc == TC_BLOCKDATA:
                self._parse_blockdata()
            elif tc == TC_ENDBLOCKDATA:
                # End of optional data block - this is expected in hierarchies
                pass
            elif tc == TC_LONGSTRING:
                self._parse_long_string()
            else:
                raise ValueError(
                    f"Unknown type code 0x{tc:02X} at offset 0x{self.pos-1:08X}"
                )

    def _register_handle(self, info: dict):
        """Register a new object and return its handle."""
        handle_idx = len(self.handles)
        info["handle_idx"] = handle_idx
        info["handle"] = self.handle_for_index(handle_idx)
        self.handles.append(info)

    def _parse_new_object(self):
        """Parse TC_OBJECT: classdesc + field values + optional annotations."""
        offset = self.pos - 1
        class_name, flags, field_names, field_types = self._parse_classdesc()

        info = {
            "type": "object",
            "offset": offset,
            "class_name": class_name,
            "flags": flags,
            "fields": {},
        }
        self._register_handle(info)

        # Read field values in order
        for fname, ftype in zip(field_names, field_types):
            field_offset = self.pos
            ref_handle = self._parse_field_value(ftype)
            info["fields"][fname] = {
                "offset": field_offset,
                "type": ftype,
                "ref_handle": ref_handle,
            }

        # Read annotations if SC_SERIALIZABLE + SC_WRITE_METHOD
        if (flags & SC_SERIALIZABLE) and (flags & SC_WRITE_METHOD):
            self._parse_annotations()
        elif (flags & SC_EXTERNALIZABLE) and (flags & SC_BLOCK_DATA):
            self._parse_annotations()

    def _parse_new_string(self):
        """Parse TC_STRING: length + UTF data."""
        offset = self.pos - 1
        length = self.read_ushort()
        s = self.read_utf(length)
        info = {"type": "string", "offset": offset, "value": s}
        self._register_handle(info)

    def _parse_new_array(self):
        """Parse TC_ARRAY."""
        offset = self.pos - 1
        class_name, flags, field_names, field_types = self._parse_classdesc()
        length = self.read_int()

        info = {
            "type": "array",
            "offset": offset,
            "class_name": class_name,
            "length": length,
            "elements": [],
        }
        self._register_handle(info)

        # Read array elements
        elem_type = class_name[1:]  # e.g. "[Ljava.lang.String;" → "java.lang.String;"
        for _ in range(length):
            elem_offset = self.pos
            ref = self._parse_field_value(elem_type)
            info["elements"].append({"offset": elem_offset, "ref_handle": ref})

    def _parse_class(self):
        """Parse TC_CLASS."""
        offset = self.pos - 1
        class_name, flags, field_names, field_types = self._parse_classdesc()
        info = {"type": "class", "offset": offset, "class_name": class_name}
        self._register_handle(info)

    def _parse_classdesc(self) -> tuple:
        """Parse a class descriptor. Returns (name, flags, field_names, field_types)."""
        tc = self.read_byte()
        if tc == TC_NULL:
            return (None, 0, [], [])
        elif tc == TC_REFERENCE:
            ref_handle = self.read_int()
            ref_idx = ref_handle - BASE_HANDLE
            if 0 <= ref_idx < len(self.handles):
                cd = self.handles[ref_idx]
                return (cd.get("class_name"), cd.get("flags", 0),
                        cd.get("field_names", []), cd.get("field_types", []))
            return (None, 0, [], [])
        elif tc != TC_CLASSDESC:
            raise ValueError(f"Expected TC_CLASSDESC, got 0x{tc:02X} at 0x{self.pos-1:X}")

        # Class name
        name_length = self.read_ushort()
        class_name = self.read_utf(name_length)

        # Serial version UID
        uid = self.read_long()

        # Register classdesc as a handle
        cd_offset = self.pos - 3 - name_length - 8  # approx
        cd_info = {
            "type": "classdesc",
            "offset": cd_offset,
            "class_name": class_name,
            "uid": uid,
        }
        self._register_handle(cd_info)

        # Class flags
        flags = self.read_byte()

        # Field count
        field_count = self.read_ushort()

        # Fields: (type_code, name) pairs
        field_names = []
        field_types = []
        for _ in range(field_count):
            type_code = chr(self.read_byte())
            fn_len = self.read_ushort()
            fn = self.read_utf(fn_len)
            field_names.append(fn)
            # Resolve full type string
            field_types.append(self._resolve_type(type_code))

        # Store field info in the classdesc handle record
        cd_info["flags"] = flags
        cd_info["field_names"] = field_names
        cd_info["field_types"] = field_types

        # End block data
        end_tc = self.read_byte()
        if end_tc != TC_ENDBLOCKDATA:
            raise ValueError(f"Expected TC_ENDBLOCKDATA, got 0x{end_tc:02X}")

        # Super class descriptor
        super_name, _, _, _ = self._parse_classdesc()
        cd_info["super_class"] = super_name

        return class_name, flags, field_names, field_types

    def _resolve_type(self, type_code: str) -> str:
        """Resolve a single-char type code to a full type string."""
        mapping = {
            'B': 'byte', 'C': 'char', 'D': 'double', 'F': 'float',
            'I': 'int', 'J': 'long', 'S': 'short', 'Z': 'boolean',
            'L': None,  # resolved later from the stream
            '[': None,  # array - resolved from stream
        }
        if type_code in mapping:
            if type_code == 'L':
                # Read the class name string
                return self._parse_field_type_string()
            elif type_code == '[':
                # Array - recursively resolve
                inner = chr(self.read_byte())
                return '[' + self._resolve_type(inner)
            return mapping[type_code]
        return type_code

    def _parse_field_type_string(self) -> str:
        """Read a field type string reference."""
        tc = self.read_byte()
        if tc == TC_STRING:
            length = self.read_ushort()
            return self.read_utf(length)
        elif tc == TC_REFERENCE:
            ref_handle = self.read_int()
            ref_idx = ref_handle - BASE_HANDLE
            if 0 <= ref_idx < len(self.handles):
                return self.handles[ref_idx].get("value", "")
        return "?"

    def _parse_field_value(self, field_type: str):
        """Parse a single field value. Returns the reference handle if this
        field is a TC_REFERENCE, otherwise None."""
        type_char = field_type[0] if field_type else 'L'

        if type_char == 'Z':  # boolean
            self.pos += 1
            return None
        elif type_char == 'B':  # byte
            self.pos += 1
            return None
        elif type_char == 'C':  # char
            self.pos += 2
            return None
        elif type_char == 'S':  # short
            self.pos += 2
            return None
        elif type_char == 'I':  # int
            self.pos += 4
            return None
        elif type_char == 'J':  # long
            self.pos += 8
            return None
        elif type_char == 'F':  # float
            self.pos += 4
            return None
        elif type_char == 'D':  # double
            self.pos += 8
            return None
        elif type_char in ('L', '['):  # object or array reference
            tc = self.read_byte()
            if tc == TC_NULL:
                return None
            elif tc == TC_REFERENCE:
                ref_handle = self.read_int()
                return ref_handle
            elif tc == TC_STRING:
                length = self.read_ushort()
                self.pos += length
                return None
            elif tc == TC_OBJECT:
                # Nested object - parse it fully
                self.pos -= 1  # pushback TC_OBJECT
                self._parse_content()
                # The handle for this nested object was just registered
                return self.handles[-1]["handle"] if self.handles else None
            elif tc == TC_ARRAY:
                self.pos -= 1
                self._parse_content()
                return self.handles[-1]["handle"] if self.handles else None
            elif tc == TC_BLOCKDATA:
                blen = self.read_byte()
                self.pos += blen
                return None
            else:
                # Unknown, skip
                return None
        else:
            return None

    def _parse_reference(self):
        """Parse TC_REFERENCE."""
        offset = self.pos - 1
        ref_handle = self.read_int()
        # Just record the reference - used during field value parsing

    def _parse_null(self):
        """Parse TC_NULL."""
        pass

    def _parse_blockdata(self):
        """Parse TC_BLOCKDATA."""
        length = self.read_byte()
        self.pos += length

    def _parse_long_string(self):
        """Parse TC_LONGSTRING."""
        length = self.read_long()
        self.pos += length

    def _parse_annotations(self):
        """Parse object annotations until TC_ENDBLOCKDATA."""
        while self.pos < len(self.data):
            tc = self.read_byte()
            if tc == TC_ENDBLOCKDATA:
                return
            elif tc == TC_OBJECT:
                self.pos -= 1
                self._parse_content()
            elif tc == TC_STRING:
                self.pos -= 1
                self._parse_content()
            elif tc == TC_REFERENCE:
                self.read_int()
            elif tc == TC_NULL:
                pass
            elif tc == TC_ARRAY:
                self.pos -= 1
                self._parse_content()
            elif tc == TC_BLOCKDATA:
                blen = self.read_byte()
                self.pos += blen
            else:
                break


def find_behavior_handles(handles: list[dict]) -> dict[int, int]:
    """Find the handle → behavior_index mapping.
    Behavior objects appear in order in the BehaviorRoot annotations hashset.
    We identify them by their class_name ending in 'Behavior' (not 'BehaviorRoot').

    Returns: {handle: behavior_index}
    """
    result = {}
    bhv_idx = -2  # First two items in hashset are IdentityHasher + string
    for h in handles:
        cn = h.get("class_name", "")
        if cn == "merlin.data.egress.scripting.Behavior":
            bhv_idx += 1
            if bhv_idx >= 0:
                result[h["handle"]] = bhv_idx
        elif cn == "merlin.data.egress.scripting.BehaviorRoot":
            bhv_idx = -2  # Reset for next BehaviorRoot
    return result


def find_agent_fields(handles: list[dict]) -> list[dict]:
    """Find all EgressAgent objects and their d_behavior/d_profile field offsets.

    Returns list of: {handle, offset, agent_name, behavior_handle, profile_handle,
                       behavior_field_offset}
    """
    agents = []
    for h in handles:
        cn = h.get("class_name", "")
        if cn == "merlin.data.egress.agents.EgressAgent":
            fields = h.get("fields", {})
            d_behavior = fields.get("d_behavior", {})
            d_profile = fields.get("d_profile", {})
            d_name = fields.get("d_name", {})
            agents.append({
                "handle": h["handle"],
                "offset": h["offset"],
                "agent_name": None,  # filled from string reference
                "behavior_handle": d_behavior.get("ref_handle"),
                "behavior_field_offset": d_behavior.get("offset"),
                "profile_handle": d_profile.get("ref_handle"),
                "profile_field_offset": d_profile.get("offset"),
            })
    return agents


def patch_file(
    data: bytearray,
    agents: list[dict],
    behavior_handle_map: dict[int, int],  # current_handle → new_handle
):
    """Patch behavior references in-place."""
    patches = 0
    for agent in agents:
        cur = agent["behavior_handle"]
        if cur is None:
            continue
        if cur not in behavior_handle_map:
            continue
        new = behavior_handle_map[cur]
        if new == cur:
            continue

        offset = agent["behavior_field_offset"]
        if offset is None:
            continue

        # The field is TC_REFERENCE (0x71) + 4-byte handle
        # We already skipped the TC_REFERENCE byte during parsing,
        # so offset points to the first byte of the handle
        struct.pack_into(">I", data, offset, new)
        patches += 1

    return patches


# ── High-level API ──────────────────────────────────────────

def build_behavior_index_map(pth_path: Path) -> tuple[dict[int, int], list[dict]]:
    """Parse .pth and return (handle→behavior_index, agents_list)."""
    import javaobj
    from javaobj.v1 import JavaObjectUnmarshaller

    with open(pth_path, 'rb') as f:
        raw = f.read()

    # 1. Parse with javaobj to get object graph
    stream = io.BytesIO(raw)
    um = JavaObjectUnmarshaller(stream)
    um.readObject()  # block data
    um.readObject()  # version
    md = um.readObject()

    # 2. Get behavior hashset ordering
    bhv_hset = md.behaviors.annotations[0]
    # Items: [0]=IdentityHasher, [1]=string, [2..] = Behavior objects
    behavior_index = {}  # behavior_object_id → index (0-9)
    bhv_idx = -2
    for item in bhv_hset.annotations:
        if hasattr(item, 'get_class') and 'Behavior' in item.get_class().name:
            bhv_idx += 1
            if bhv_idx >= 0:
                behavior_index[id(item)] = bhv_idx

    # 3. Build agent → new_behavior mapping using pathfinder_inject logic
    # Import the inject logic
    import pathfinder_inject as pinj

    csv_rows = pinj.read_csv_rows(pinj.DEFAULT_CSV)
    aco_map = pinj.build_sg_exit_map(csv_rows, "ACO")
    adaptive_map = pinj.build_sg_exit_map(csv_rows, "AdaptiveSingleNextHop")
    sg_meta = pinj.build_sg_meta(csv_rows)

    # Get all EgressAgent objects
    top_hset = md.agents.annotations[0]
    all_agents = []
    for item in top_hset.annotations:
        if not hasattr(item, 'get_class') or 'EgressAgentComp' not in item.get_class().name:
            continue
        if not item.annotations:
            continue
        sub_hset = item.annotations[0]
        if not hasattr(sub_hset, 'annotations'):
            continue
        for sub_item in sub_hset.annotations:
            if hasattr(sub_item, 'get_class') and 'EgressAgent' in sub_item.get_class().name and 'Comp' not in sub_item.get_class().name:
                all_agents.append(sub_item)

    # Build occupant list compatible with pathfinder_inject logic
    # We need: id, profile, behavior, loc
    occupants = []
    agent_obj_map = {}  # occupant_id → JavaObject
    for agent in all_agents:
        name = getattr(agent, 'd_name', '?')
        profile_obj = getattr(agent, 'd_profile', None)
        behavior_obj = getattr(agent, 'd_behavior', None)
        location = getattr(agent, 'd_location', None)

        # Determine profile index
        profile_idx = -1
        if profile_obj is not None and hasattr(profile_obj, 'get_class'):
            # Check if it matches DEFAULT or NO_CHANGE
            if profile_obj is md.profiles.DEFAULT:
                profile_idx = 0  # Default profile
            elif hasattr(md.profiles, 'NO_CHANGE') and profile_obj is md.profiles.NO_CHANGE:
                profile_idx = -1

        # Get position from location
        loc = "0 0 0"
        if location is not None and hasattr(location, 'point'):
            pt = location.point
            if hasattr(pt, 'x') and hasattr(pt, 'y') and hasattr(pt, 'z'):
                loc = f"{pt.x} {pt.y} {pt.z}"

        # Determine behavior index
        old_bhv_idx = behavior_index.get(id(behavior_obj), -1)

        occ = {
            "id": hash(name) % 1000000,  # approximate unique ID
            "profile": profile_idx,
            "behavior": old_bhv_idx,
            "loc": loc,
            "_java_obj": agent,
        }
        occupants.append(occ)
        agent_obj_map[occ["id"]] = agent

    # Run the assignment logic
    assignments = pinj.assign_exits(occupants, aco_map, adaptive_map, sg_meta)

    # Build behavior handle mapping
    # behavior_index → Behavior JavaObject (reverse map)
    idx_to_bhv_obj = {}
    for obj_id, idx in behavior_index.items():
        idx_to_bhv_obj[idx] = obj_id

    # Get the handle for each Behavior JavaObject
    # We need to match JavaObject identity to handle from the reference table
    # The javaobj reference table maps handles to actual objects
    # Use the unmarshaller's _references (internal)

    return behavior_index, occupants, assignments, all_agents


# ── Main ────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Binary patch Pathfinder .pth behavior references")
    parser.add_argument("--pth", type=Path, default=ROOT / "pathfinder" / "龙阳路my .pth")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.out is None:
        stem = args.pth.stem
        args.out = args.pth.parent / f"{stem}_injected.pth"

    print(f"[1] Loading: {args.pth}")
    behavior_index, occupants, assignments, all_agents = build_behavior_index_map(args.pth)

    print(f"    Behaviors found: {len(behavior_index)}")
    print(f"    Agents found: {len(all_agents)}")

    # TODO: binary parse and patch once the mapping is confirmed
    print("\n[2] Analyzing changes...")
    changes = 0
    for occ in occupants:
        old_bhv = occ["behavior"]
        new_exit = assignments.get(occ["id"])
        if new_exit is None:
            continue
        new_bhv = pinj.EXIT_TO_BEHAVIOR.get(new_exit)
        if new_bhv is not None and new_bhv != old_bhv:
            changes += 1

    print(f"    Agents to change: {changes}/{len(occupants)}")

    if args.dry_run:
        print("\n[Dry-run] Done.")
        return

    print(f"\n[3] Writing: {args.out}")
    # Binary patching will go here
    print("    (Binary patching not yet implemented)")


if __name__ == "__main__":
    main()
