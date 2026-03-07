from typing import override

from pydantic import BaseModel


class IntRange(BaseModel):
    start: int
    end: int

    def extend(self, new: int) -> bool:
        if new == self.start - 1:
            self.start = new
            return True
        elif new == self.end + 1:
            self.end = new
            return True
        else:
            return False

    def contains(self, new: int) -> bool:
        return self.start <= new <= self.end

    @override
    def __str__(self) -> str:
        if self.start == self.end:
            return str(self.start)
        else:
            return f"{self.start}-{self.end}"


class Ranges(BaseModel):
    ranges: list[IntRange]

    def add(self, item: int) -> bool:
        done = False
        for r in self.ranges:
            if r.extend(item):
                self.__merge_ranges()
                done = True
            elif r.contains(item):
                return False
        if not done:
            self.ranges.append(IntRange(start=item, end=item))
            self.ranges.sort(key=lambda r: r.start)
        self.__merge_ranges()
        return True

    def remove(self, chapter: int) -> bool:
        new_ranges: list[IntRange] = []
        res = False
        for r in self.ranges:
            if r.start <= chapter <= r.end:
                res = True
                if r.start == chapter:
                    if r.end > chapter:
                        new_ranges.append(IntRange(start=chapter + 1, end=r.end))
                elif r.end == chapter:
                    if r.start < chapter:
                        new_ranges.append(IntRange(start=r.start, end=chapter - 1))
                else:
                    new_ranges.append(IntRange(start=r.start, end=chapter - 1))
                    new_ranges.append(IntRange(start=chapter + 1, end=r.end))
            else:
                new_ranges.append(r)
        self.ranges = new_ranges
        return res

    def __merge_ranges(self) -> None:
        self.ranges.sort(key=lambda r: r.start)
        new_ranges: list[IntRange] = []
        last_range = self.ranges[0]
        for r in self.ranges[1:]:
            if last_range.end + 1 >= r.start:
                last_range = IntRange(
                    start=min(last_range.start, r.start),
                    end=max(last_range.end, r.end),
                )
            else:
                new_ranges.append(last_range)
                last_range = r
        new_ranges.append(last_range)
        self.ranges = new_ranges

    @override
    def __str__(self) -> str:
        return ", ".join([str(r) for r in self.ranges])

    @property
    def end(self):
        return self.ranges[-1].end

    def chapters(self):
        for r in self.ranges:
            for i in range(r.start, r.end + 1):
                yield i

    @staticmethod
    def new():
        return Ranges(ranges=[])
