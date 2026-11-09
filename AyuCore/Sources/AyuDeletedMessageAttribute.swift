import Foundation
import Postbox

/// Атрибут сообщения Postbox, фиксирующий факт и время удаленного удаления сообщения
public final class AyuDeletedMessageAttribute: MessageAttribute {
    public let deletedAt: Int32
    public let originalTimestamp: Int32

    public init(deletedAt: Int32, originalTimestamp: Int32) {
        self.deletedAt = deletedAt
        self.originalTimestamp = originalTimestamp
    }

    public required init(decoder: PostboxDecoder) {
        self.deletedAt = decoder.decodeInt32ForKey("deletedAt", orElse: 0)
        self.originalTimestamp = decoder.decodeInt32ForKey("originalTimestamp", orElse: 0)
    }

    public func encode(_ encoder: PostboxEncoder) {
        encoder.encodeInt32(self.deletedAt, forKey: "deletedAt")
        encoder.encodeInt32(self.originalTimestamp, forKey: "originalTimestamp")
    }

    public func description(indent: Int = 0) -> String {
        return "AyuDeletedMessageAttribute(deletedAt: \(self.deletedAt), originalTimestamp: \(self.originalTimestamp))"
    }
}
