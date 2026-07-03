// The Kinesis mark, cropped from the master logo. It's always presented on its
// intended dark tile with a hairline ring, so the metallic K reads correctly in
// both the dark and light themes.
export default function LogoMark({
  size = 28,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={`inline-grid shrink-0 place-items-center overflow-hidden rounded-[7px] bg-black ring-1 ring-white/10 ${className}`}
      style={{ width: size, height: size }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/kinesis-mark.png"
        alt="Kinesis"
        width={size}
        height={size}
        className="h-full w-full object-cover"
      />
    </span>
  );
}
